from __future__ import annotations

import base64
import binascii
import ipaddress
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile, status

from source.config.settings import settings
from source.db.session import db_session_manager
from source.integrations import IntegrationSyncError, LiveScoreProviderClient, ProviderPayloadMapper, RankingsProviderClient
from source.repositories import AdminSupportRepository, AuditRepository, MatchRepository
from source.schemas.pydantic.admin import (
    AdminActionResult,
    AdminIntegrationDetail,
    AdminIntegrationItem,
    AdminIntegrationLogItem,
    AdminIntegrationLogSummary,
    AdminIntegrationSummary,
    AdminIntegrationSyncResult,
    AdminIntegrationUpdateResult,
    AdminMediaItem,
    AdminMediaSummary,
    AuditLogItem,
    AuditLogSummary,
)
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.media import MediaFile
from source.services.log_service import LogService


class OperationsService:
    def __init__(self) -> None:
        self.storage_dir = Path('var')
        self.media_dir = self.storage_dir / 'media'
        self.media_index_file = self.storage_dir / 'media_index.json'
        self.integrations_file = self.storage_dir / 'integrations.json'
        self.audit_repo = AuditRepository()
        self.admin_support = AdminSupportRepository()
        self.matches = MatchRepository()
        self.mapper = ProviderPayloadMapper()
        self.logs = LogService()

    def _ensure_storage(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _audit_changed_keys(before_json: dict | None, after_json: dict | None) -> list[str]:
        before_payload = before_json or {}
        after_payload = after_json or {}
        keys = sorted(set(before_payload) | set(after_payload))
        return [key for key in keys if before_payload.get(key) != after_payload.get(key)]

    def _to_audit_log_item(self, item) -> AuditLogItem:
        changed_keys = self._audit_changed_keys(item.before_json, item.after_json)
        return AuditLogItem(
            id=item.id,
            user_id=item.user_id,
            action=item.action,
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            before_json=item.before_json,
            after_json=item.after_json,
            changed_keys=changed_keys,
            changed_fields_count=len(changed_keys),
            created_at=item.created_at,
        )

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text())

    def _write_json(self, path: Path, payload: Any) -> None:
        self._ensure_storage()
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))

    async def _log_audit(self, *, action: str, entity_type: str, entity_id: int | None = None, before_json: dict | None = None, after_json: dict | None = None, user_id: int | None = None) -> None:
        async with db_session_manager.session() as session:
            await self.audit_repo.create(session, {'user_id': user_id, 'action': action, 'entity_type': entity_type, 'entity_id': entity_id, 'before_json': before_json, 'after_json': after_json})

    def _media_records(self) -> list[dict]:
        return self._read_json(self.media_index_file, [])

    def _save_media_records(self, payload: list[dict]) -> None:
        self._write_json(self.media_index_file, payload)

    @staticmethod
    def _media_item(payload: dict) -> MediaFile:
        return MediaFile(id=payload['id'], filename=payload['filename'], content_type=payload['content_type'], url=payload['url'], size=payload.get('size'))

    @staticmethod
    def _admin_media_item(payload: dict) -> AdminMediaItem:
        stored_path = str(payload.get('stored_path') or '')
        created_at = payload.get('created_at')
        resolved_created_at = datetime.fromisoformat(created_at) if created_at else None
        return AdminMediaItem(
            id=payload['id'],
            filename=payload['filename'],
            content_type=payload['content_type'],
            url=payload['url'],
            size=payload.get('size'),
            created_at=resolved_created_at,
            exists=bool(stored_path) and Path(stored_path).exists(),
            stored_path=stored_path,
        )

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        candidate = Path(filename).name.strip().replace('\x00', '')
        candidate = re.sub(r'[^A-Za-z0-9._-]+', '_', candidate)
        candidate = candidate.lstrip('._')
        return candidate

    def _validate_upload(self, filename: str, content_type: str, size: int) -> None:
        if not filename:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='filename is required')
        if any(ord(char) < 32 for char in filename) or '\x00' in filename:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Unsafe filename')
        if filename != Path(filename).name or '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Unsafe filename')
        extension = Path(filename).suffix.lower()
        if extension in set(settings.media.forbidden_extensions):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Forbidden file extension')
        if content_type not in settings.media.allowed_content_types:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Unsupported media type')
        allowed_extensions = settings.media.allowed_extensions_by_content_type.get(content_type, [])
        if extension not in allowed_extensions:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='File extension does not match content type')
        if size > settings.media.max_upload_size_bytes:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='File too large')

    @staticmethod
    def _decode_media_content(payload: dict[str, Any]) -> bytes:
        content_base64 = payload.get('content_base64')
        if content_base64 not in (None, ''):
            try:
                return base64.b64decode(str(content_base64), validate=True)
            except (ValueError, binascii.Error) as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid base64 payload') from exc
        raw_content = payload.get('content', '')
        if isinstance(raw_content, bytes):
            return raw_content
        return str(raw_content).encode('utf-8')

    @staticmethod
    def _validate_content_signature(content_type: str, content: bytes) -> None:
        if not content:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Empty file content')
        if content_type == 'image/jpeg':
            if not (content.startswith(b'\xff\xd8\xff') and content.endswith(b'\xff\xd9')):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid JPEG file signature')
            return
        if content_type == 'image/png':
            if not content.startswith(b'\x89PNG\r\n\x1a\n'):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid PNG file signature')
            return
        if content_type == 'image/gif':
            if not (content.startswith(b'GIF87a') or content.startswith(b'GIF89a')):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid GIF file signature')
            return
        if content_type == 'image/webp':
            if not (len(content) >= 12 and content.startswith(b'RIFF') and content[8:12] == b'WEBP'):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid WEBP file signature')
            return
        if content_type == 'text/plain':
            try:
                decoded = content.decode('utf-8')
            except UnicodeDecodeError as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid UTF-8 text payload') from exc
            if '\x00' in decoded:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Binary content is not allowed for text/plain')

    async def list_media(self) -> SuccessResponse[list[MediaFile]]:
        return SuccessResponse(data=[self._media_item(item) for item in self._media_records()])

    async def list_admin_media(
        self,
        *,
        content_type: str | None = None,
        exists: bool | None = None,
        limit: int = 200,
    ) -> SuccessResponse[list[AdminMediaItem]]:
        records = self._media_records()
        payload: list[AdminMediaItem] = []
        for item in sorted(records, key=lambda value: (str(value.get('created_at') or ''), int(value.get('id') or 0)), reverse=True):
            model = self._admin_media_item(item)
            if content_type and model.content_type != content_type:
                continue
            if exists is not None and model.exists != exists:
                continue
            payload.append(model)
            if len(payload) >= max(1, min(limit, 500)):
                break
        return SuccessResponse(data=payload)

    async def summarize_media(self) -> SuccessResponse[AdminMediaSummary]:
        content_types: dict[str, int] = {}
        total_size_bytes = 0
        missing_files = 0
        latest_created_at = None
        items = [self._admin_media_item(item) for item in self._media_records()]
        largest_item = None
        indexed_paths = {item.stored_path for item in items if item.stored_path}
        files_on_disk = [item for item in self.media_dir.glob('*') if item.is_file()] if self.media_dir.exists() else []
        orphan_files = sum(1 for item in files_on_disk if str(item) not in indexed_paths)
        for item in items:
            content_types[item.content_type] = content_types.get(item.content_type, 0) + 1
            total_size_bytes += int(item.size or 0)
            if not item.exists:
                missing_files += 1
            if item.created_at is not None and (latest_created_at is None or item.created_at > latest_created_at):
                latest_created_at = item.created_at
            if largest_item is None or int(item.size or 0) > int(largest_item.size or 0):
                largest_item = item
        return SuccessResponse(
            data=AdminMediaSummary(
                total=len(items),
                total_size_bytes=total_size_bytes,
                missing_files=missing_files,
                orphan_files=orphan_files,
                content_types=content_types,
                latest_created_at=latest_created_at,
                storage_backend='local_fs',
                storage_path=str(self.media_dir),
                writable=self.media_dir.exists() and self.media_dir.is_dir(),
                indexed_files=len(items),
                files_on_disk=len(files_on_disk),
            ),
            meta={
                'healthy': missing_files == 0 and orphan_files == 0,
                'largest_file': {
                    'id': largest_item.id,
                    'filename': largest_item.filename,
                    'size': largest_item.size,
                } if largest_item is not None else None,
            },
        )

    async def get_media(self, media_id: int) -> SuccessResponse[MediaFile]:
        record = next((item for item in self._media_records() if item['id'] == media_id), None)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Media not found')
        return SuccessResponse(data=self._media_item(record))

    async def get_admin_media(self, media_id: int) -> SuccessResponse[AdminMediaItem]:
        record = next((item for item in self._media_records() if item['id'] == media_id), None)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Media not found')
        return SuccessResponse(data=self._admin_media_item(record))

    async def upload_media_file(self, file: UploadFile) -> SuccessResponse[MediaFile]:
        raw_filename = (file.filename or '').strip()
        self._validate_upload(raw_filename, file.content_type or 'application/octet-stream', 0)
        filename = self._sanitize_filename(raw_filename)
        content_type = file.content_type or 'application/octet-stream'
        records = self._media_records()
        media_id = max((item['id'] for item in records), default=0) + 1
        self._ensure_storage()
        file_path = self.media_dir / f'{media_id}_{filename}'
        content = await file.read()
        self._validate_upload(raw_filename, content_type, len(content))
        self._validate_content_signature(content_type, content)
        file_path.write_bytes(content)
        record = {'id': media_id, 'filename': filename, 'content_type': content_type, 'url': f'/static-runtime/media/{file_path.name}', 'size': len(content), 'stored_path': str(file_path), 'created_at': datetime.now(tz=UTC).isoformat()}
        records.append(record)
        self._save_media_records(records)
        await self._log_audit(action='media.upload', entity_type='media', entity_id=media_id, after_json=record)
        return SuccessResponse(data=self._media_item(record))

    async def create_media_record(self, payload: dict[str, Any]) -> SuccessResponse[MediaFile]:
        raw_filename = str(payload.get('filename', '')).strip()
        filename = self._sanitize_filename(raw_filename)
        content_type = str(payload.get('content_type') or 'application/octet-stream')
        content = self._decode_media_content(payload)
        self._validate_upload(raw_filename, content_type, int(payload.get('size') or len(content)))
        self._validate_content_signature(content_type, content)
        records = self._media_records()
        media_id = max((item['id'] for item in records), default=0) + 1
        self._ensure_storage()
        file_path = self.media_dir / f'{media_id}_{filename}'
        file_path.write_bytes(content)
        record = {'id': media_id, 'filename': filename, 'content_type': content_type, 'url': f'/static-runtime/media/{file_path.name}', 'size': int(payload.get('size') or len(content)), 'stored_path': str(file_path), 'created_at': datetime.now(tz=UTC).isoformat()}
        records.append(record)
        self._save_media_records(records)
        await self._log_audit(action='admin.media.upload', entity_type='media', entity_id=media_id, after_json=record)
        return SuccessResponse(data=self._media_item(record))

    async def delete_media(self, media_id: int) -> SuccessResponse[AdminActionResult]:
        records = self._media_records()
        record = next((item for item in records if item['id'] == media_id), None)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Media not found')
        records = [item for item in records if item['id'] != media_id]
        self._save_media_records(records)
        stored_path = Path(record.get('stored_path', ''))
        if stored_path.exists():
            stored_path.unlink()
        await self._log_audit(action='media.delete', entity_type='media', entity_id=media_id, before_json=record)
        return SuccessResponse(
            data=AdminActionResult(
                entity_type='media',
                action='delete',
                status='ok',
                entity_id=media_id,
                message='Media deleted',
                details={'filename': record.get('filename'), 'url': record.get('url')},
            )
        )

    def _integration_records(self) -> dict[str, dict]:
        return self._read_json(self.integrations_file, {})

    def _save_integration_records(self, payload: dict[str, dict]) -> None:
        self._write_json(self.integrations_file, payload)

    @staticmethod
    def _validate_integration_endpoint(endpoint: str) -> str:
        candidate = endpoint.strip()
        if not candidate:
            return ''
        parsed = urlparse(candidate)
        if parsed.scheme not in {'http', 'https'}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Integration endpoint must use http or https')
        if not parsed.netloc or not parsed.hostname:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Integration endpoint hostname is required')
        if parsed.username or parsed.password:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Credentials in integration endpoint are not allowed')
        hostname = parsed.hostname.lower()
        if hostname in {'localhost', 'localhost.localdomain'}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Local integration endpoints are not allowed')
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            ip = None
        if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Private integration endpoints are not allowed')
        return candidate

    @staticmethod
    def _normalize_integration_settings(payload: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            if value in (None, ''):
                continue
            if key == 'endpoint':
                normalized[key] = OperationsService._validate_integration_endpoint(str(value))
                continue
            if key == 'headers':
                if not isinstance(value, dict):
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Integration headers must be an object')
                normalized[key] = {str(header_key): str(header_value) for header_key, header_value in value.items()}
                continue
            if key == 'timeout_seconds':
                timeout = float(value)
                if timeout <= 0 or timeout > 30:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Integration timeout_seconds is out of range')
                normalized[key] = timeout
                continue
            if key == 'max_attempts':
                attempts = int(value)
                if attempts < 1 or attempts > 5:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Integration max_attempts is out of range')
                normalized[key] = attempts
                continue
            normalized[key] = value
        return normalized

    def _integration_client(self, provider: str, settings_payload: dict[str, Any] | None = None):
        settings_payload = settings_payload or {}
        timeout_seconds = float(settings_payload.get('timeout_seconds') or 5.0)
        max_attempts = int(settings_payload.get('max_attempts') or 3)
        if 'live' in provider:
            return LiveScoreProviderClient(provider, timeout_seconds=timeout_seconds, max_attempts=max_attempts)
        if 'rank' in provider:
            return RankingsProviderClient(provider, timeout_seconds=timeout_seconds, max_attempts=max_attempts)
        return None

    async def _apply_live_provider_events(self, provider: str, events) -> int:
        from source.services.live_hub import live_hub
        from source.services.workflow_service import WorkflowService

        workflows = WorkflowService()
        applied = 0
        async with db_session_manager.session() as session:
            for event in events:
                match = await self.matches.get_by_slug(session, event.match_slug)
                if match is None:
                    continue
                provider_event_key = f'{provider}:{event.match_slug}:{event.event_type}:{event.occurred_at.isoformat()}'
                duplicate = await self.matches.find_event_by_provider_key(session, match_id=match.id, provider_event_key=provider_event_key)
                if duplicate is not None:
                    continue
                existing_events = await self.matches.get_events(session, match.id)
                latest_provider_event_at = max(
                    (
                        item.created_at.replace(tzinfo=UTC) if item.created_at is not None and item.created_at.tzinfo is None else item.created_at
                        for item in existing_events
                        if (item.payload_json or {}).get('provider') == provider and item.created_at is not None
                    ),
                    default=None,
                )
                if latest_provider_event_at is not None and latest_provider_event_at > event.occurred_at:
                    continue
                status_changed = match.status != event.status
                score_changed = bool(event.score_summary and event.score_summary != match.score_summary)
                if status_changed or score_changed:
                    update_payload = {}
                    if status_changed:
                        update_payload['status'] = event.status
                    if score_changed:
                        update_payload['score_summary'] = event.score_summary
                    await self.matches.update(session, match, update_payload)
                payload_json = dict(event.payload)
                payload_json['provider'] = provider
                payload_json['provider_event_key'] = provider_event_key
                created = await self.matches.create_event(session, {
                    'match_id': match.id,
                    'event_type': event.event_type,
                    'set_number': payload_json.get('set_number'),
                    'game_number': payload_json.get('game_number'),
                    'player_id': payload_json.get('player_id'),
                    'payload_json': payload_json,
                    'created_at': event.occurred_at,
                })
                applied += 1
                if status_changed:
                    await workflows.process_match_status_change(match.id, event.status)
                await workflows.process_match_event(match.id, event_type=event.event_type, set_number=payload_json.get('set_number'), payload_json=payload_json)
                await live_hub.broadcast(
                    channels=[f'live:all', f'live:match:{match.id}', f'live:tournament:{match.tournament_id}', f'live:player:{match.player1_id}', f'live:player:{match.player2_id}'],
                    payload={'type': event.event_type if event.event_type in {'score_updated', 'point_updated', 'break_point', 'set_finished', 'match_finished'} else 'match_status_changed', 'match_id': match.id, 'payload': {'event_id': created.id, 'status': event.status, 'score_summary': event.score_summary, **payload_json}},
                )
        return applied

    async def _apply_ranking_provider_rows(self, provider: str, rows) -> int:
        from source.services.workflow_service import WorkflowService

        if not rows:
            return 0
        workflows = WorkflowService()
        async with db_session_manager.session() as session:
            names = [row.player_name for row in rows]
            players = {item.full_name: item for item in await self.admin_support.find_players_by_names(session, names)}
            if len(players) != len(set(names)):
                missing = sorted(set(names) - set(players))
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'Players not found for rankings import: {", ".join(missing)}')
            existing_snapshots = [item for item in await self.admin_support.list_ranking_snapshots(session) if item.ranking_type == rows[0].ranking_type]
            latest_existing_date = max((item.ranking_date for item in existing_snapshots), default=None)
            previous = {item.player_id: item for item in await self.admin_support.get_previous_rankings(session, rows[0].ranking_type, rows[0].ranking_date)}
            ranking_rows = []
            for row in rows:
                player = players[row.player_name]
                movement = row.movement
                if movement is None:
                    previous_entry = previous.get(player.id)
                    movement = 0 if previous_entry is None else int(previous_entry.rank_position) - int(row.position)
                ranking_rows.append({
                    'ranking_type': row.ranking_type,
                    'ranking_date': row.ranking_date,
                    'player_id': player.id,
                    'rank_position': row.position,
                    'points': row.points,
                    'movement': movement,
                })
            await self.admin_support.replace_rankings(session, ranking_type=rows[0].ranking_type, ranking_date=rows[0].ranking_date, rows=ranking_rows)
            if latest_existing_date is None or rows[0].ranking_date >= latest_existing_date:
                affected_player_ids = [item.player_id for item in existing_snapshots]
                await self.admin_support.clear_player_current_rankings(session, sorted(set(affected_player_ids) - {row['player_id'] for row in ranking_rows}))
                await self.admin_support.apply_player_current_rankings(session, ranking_rows)
            await self.admin_support.commit(session)
        await workflows.process_ranking_updates(ranking_rows, ranking_type=rows[0].ranking_type, ranking_date=rows[0].ranking_date)
        return len(rows)

    async def list_integrations(self, *, provider: str | None = None, status: str | None = None) -> SuccessResponse[list[AdminIntegrationItem]]:
        records = self._integration_records()
        data = []
        for provider_name, item in sorted(records.items()):
            integration_status = item.get('status', 'configured')
            if provider and provider.lower() not in provider_name.lower():
                continue
            if status and integration_status != status:
                continue
            data.append(
                AdminIntegrationItem(
                    provider=provider_name,
                    status=integration_status,
                    last_sync_at=datetime.fromisoformat(item['last_sync_at']) if item.get('last_sync_at') else None,
                    last_error=item.get('last_error'),
                    logs_count=len(item.get('logs') or []),
                )
            )
        return SuccessResponse(data=data, meta={'total': len(data), 'filters': {'provider': provider, 'status': status}})

    async def summarize_integrations(self) -> SuccessResponse[AdminIntegrationSummary]:
        records = self._integration_records()
        by_status: dict[str, int] = {}
        latest_sync_at = None
        with_errors = 0
        providers = sorted(records.keys())
        for item in records.values():
            status_value = str(item.get('status') or 'configured')
            by_status[status_value] = by_status.get(status_value, 0) + 1
            if item.get('last_error'):
                with_errors += 1
            raw_last_sync_at = item.get('last_sync_at')
            if raw_last_sync_at:
                parsed = datetime.fromisoformat(str(raw_last_sync_at))
                if latest_sync_at is None or parsed > latest_sync_at:
                    latest_sync_at = parsed
        return SuccessResponse(
            data=AdminIntegrationSummary(
                total=len(records),
                by_status=by_status,
                with_errors=with_errors,
                latest_sync_at=latest_sync_at,
                providers=providers,
            )
        )

    async def update_integration(self, provider: str, payload: dict[str, Any]) -> SuccessResponse[AdminIntegrationUpdateResult]:
        records = self._integration_records()
        current = records.get(provider, {'status': 'configured', 'last_sync_at': None, 'last_error': None, 'settings': {}, 'logs': []})
        normalized_payload = self._normalize_integration_settings(payload)
        updated = current | {'settings': current.get('settings', {}) | normalized_payload}
        records[provider] = updated
        self._save_integration_records(records)
        await self._log_audit(action='integration.update', entity_type='integration', entity_id=None, before_json=current, after_json=updated)
        return SuccessResponse(
            data=AdminIntegrationUpdateResult(
                provider=provider,
                status=str(updated.get('status') or 'configured'),
                last_sync_at=datetime.fromisoformat(updated['last_sync_at']) if updated.get('last_sync_at') else None,
                last_error=updated.get('last_error'),
                settings=dict(updated.get('settings') or {}),
            ),
            meta={'updated_keys': sorted(normalized_payload.keys())},
        )

    async def get_integration_detail(self, provider: str) -> SuccessResponse[AdminIntegrationDetail]:
        records = self._integration_records()
        current = records.get(provider)
        if current is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Integration not found')
        logs = current.get('logs') or []
        latest_log = logs[-1] if logs else None
        return SuccessResponse(
            data=AdminIntegrationDetail(
                provider=provider,
                status=str(current.get('status') or 'configured'),
                last_sync_at=datetime.fromisoformat(current['last_sync_at']) if current.get('last_sync_at') else None,
                last_error=current.get('last_error'),
                settings=dict(current.get('settings') or {}),
                logs_count=len(logs),
                latest_log_at=datetime.fromisoformat(latest_log['timestamp']) if latest_log and latest_log.get('timestamp') else None,
                latest_log_level=str(latest_log.get('level')) if latest_log and latest_log.get('level') else None,
                storage_backend='local_json',
                storage_path=str(self.integrations_file),
            ),
            meta={'available_logs': len(logs)},
        )

    async def sync_integration(self, provider: str, payload: dict[str, Any] | None = None) -> SuccessResponse[AdminIntegrationSyncResult]:
        records = self._integration_records()
        current = records.get(provider, {'status': 'configured', 'last_sync_at': None, 'last_error': None, 'settings': {}, 'logs': []})
        payload = payload or {}
        provider_payload = payload.get('provider_payload')
        log_message = 'Manual sync executed'
        applied = 0
        sync_mode = 'noop'
        started_at = time.perf_counter()
        try:
            if isinstance(provider_payload, dict):
                sync_mode = 'provider_payload'
                if 'live' in provider:
                    events = self.mapper.parse_live_events(provider, provider_payload)
                    applied = await self._apply_live_provider_events(provider, events)
                    log_message = f'Validated {len(events)} live events from provider payload, applied {applied}'
                elif 'rank' in provider:
                    rows = self.mapper.parse_rankings(provider, provider_payload)
                    applied = len(rows)
                    log_message = f'Validated {len(rows)} ranking rows from provider payload'
            else:
                endpoint = self._validate_integration_endpoint(str(payload.get('endpoint') or current.get('settings', {}).get('endpoint') or ''))
                headers = current.get('settings', {}).get('headers') or {}
                client = self._integration_client(provider, current.get('settings', {}))
                if endpoint and client is not None:
                    sync_mode = 'remote_fetch'
                    if 'live' in provider:
                        events = await client.fetch_events(endpoint, headers=headers)
                        applied = await self._apply_live_provider_events(provider, events)
                        log_message = f'Fetched {len(events)} live events from provider endpoint, applied {applied}'
                    elif 'rank' in provider:
                        rows = await client.fetch_rankings(endpoint, headers=headers)
                        applied = await self._apply_ranking_provider_rows(provider, rows)
                        log_message = f'Fetched {len(rows)} ranking rows from provider endpoint, applied {applied}'
                elif not endpoint and not isinstance(provider_payload, dict):
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Integration endpoint or provider_payload is required')
            log_entry = {'timestamp': datetime.now(tz=UTC).isoformat(), 'level': 'info', 'message': log_message}
            updated = current | {'status': 'ok', 'last_sync_at': log_entry['timestamp'], 'last_error': None, 'logs': [*current.get('logs', []), log_entry][-20:]}
            records[provider] = updated
            self._save_integration_records(records)
            await self._log_audit(action='integration.sync', entity_type='integration', entity_id=None, before_json=current, after_json=updated)
            duration_ms = max(int((time.perf_counter() - started_at) * 1000), 0)
            return SuccessResponse(
                data=AdminIntegrationSyncResult(
                    provider=provider,
                    status=str(updated.get('status') or 'ok'),
                    last_sync_at=datetime.fromisoformat(updated['last_sync_at']) if updated.get('last_sync_at') else None,
                    last_error=updated.get('last_error'),
                    message=log_message,
                    applied_count=applied,
                    logs_count=len(updated.get('logs') or []),
                    sync_mode=sync_mode,
                    duration_ms=duration_ms,
                ),
                meta={'sync_mode': sync_mode, 'provider_has_endpoint': bool(current.get('settings', {}).get('endpoint') or payload.get('endpoint')), 'used_payload': isinstance(provider_payload, dict), 'duration_ms': duration_ms, 'storage_backend': 'local_json'},
            )
        except IntegrationSyncError as exc:
            log_entry = {'timestamp': datetime.now(tz=UTC).isoformat(), 'level': 'error', 'message': f'Provider sync failed: {exc}'}
            updated = current | {'status': 'error', 'last_sync_at': log_entry['timestamp'], 'last_error': str(exc), 'logs': [*current.get('logs', []), log_entry][-20:]}
            records[provider] = updated
            self._save_integration_records(records)
            await self._log_audit(action='integration.sync.failed', entity_type='integration', entity_id=None, before_json=current, after_json=updated)
            self.logs.write('integration', level='error', message=f'Provider sync failed: {exc}', context={'provider': provider, 'status': 'error'})
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    async def get_integration_logs(
        self,
        provider: str,
        *,
        level: str | None = None,
        limit: int = 100,
    ) -> SuccessResponse[list[AdminIntegrationLogItem]]:
        records = self._integration_records()
        current = records.get(provider)
        if current is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Integration not found')
        logs = current.get('logs', [])
        payload = [
            AdminIntegrationLogItem(
                timestamp=datetime.fromisoformat(item['timestamp']),
                level=str(item.get('level') or 'info'),
                message=str(item.get('message') or ''),
            )
            for item in logs
            if item.get('timestamp') and item.get('message') and (level is None or str(item.get('level') or 'info') == level)
        ]
        limited = payload[-max(1, min(limit, 500)):]
        return SuccessResponse(data=limited, meta={'total': len(payload), 'returned': len(limited), 'level': level})

    async def summarize_integration_logs(self, provider: str) -> SuccessResponse[AdminIntegrationLogSummary]:
        records = self._integration_records()
        current = records.get(provider)
        if current is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Integration not found')
        by_level: dict[str, int] = {}
        latest_at = None
        total = 0
        for item in current.get('logs', []):
            if not item.get('timestamp') or not item.get('message'):
                continue
            total += 1
            level_value = str(item.get('level') or 'info')
            by_level[level_value] = by_level.get(level_value, 0) + 1
            parsed = datetime.fromisoformat(item['timestamp'])
            if latest_at is None or parsed > latest_at:
                latest_at = parsed
        return SuccessResponse(
            data=AdminIntegrationLogSummary(
                provider=provider,
                total=total,
                by_level=by_level,
                latest_at=latest_at,
            ),
            meta={'storage_path': str(self.integrations_file)},
        )

    async def list_audit_logs(
        self,
        *,
        user_id: int | None = None,
        entity_type: str | None = None,
        action: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
    ) -> SuccessResponse[list[AuditLogItem]]:
        async with db_session_manager.session() as session:
            items = await self.audit_repo.list(
                session,
                user_id=user_id,
                entity_type=entity_type,
                action=action,
                date_from=date_from,
                date_to=date_to,
                limit=max(1, min(limit, 500)),
            )
            return SuccessResponse(data=[self._to_audit_log_item(item) for item in items])

    async def summarize_audit_logs(
        self,
        *,
        user_id: int | None = None,
        entity_type: str | None = None,
        action: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> SuccessResponse[AuditLogSummary]:
        async with db_session_manager.session() as session:
            items = await self.audit_repo.list(
                session,
                user_id=user_id,
                entity_type=entity_type,
                action=action,
                date_from=date_from,
                date_to=date_to,
            )
        by_action: dict[str, int] = {}
        by_entity_type: dict[str, int] = {}
        latest_at = None
        for item in items:
            by_action[item.action] = by_action.get(item.action, 0) + 1
            by_entity_type[item.entity_type] = by_entity_type.get(item.entity_type, 0) + 1
            if latest_at is None or item.created_at > latest_at:
                latest_at = item.created_at
        return SuccessResponse(
            data=AuditLogSummary(
                total=len(items),
                by_action=by_action,
                by_entity_type=by_entity_type,
                latest_at=latest_at,
            )
        )

    async def get_audit_log(self, log_id: int) -> SuccessResponse[AuditLogItem]:
        async with db_session_manager.session() as session:
            item = await self.audit_repo.get(session, log_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Audit log not found')
            return SuccessResponse(data=self._to_audit_log_item(item))
