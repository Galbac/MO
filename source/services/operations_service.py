from __future__ import annotations

import base64
import binascii
import ipaddress
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile, status

from source.config.settings import settings
from source.db.session import db_session_manager
from source.integrations import IntegrationSyncError, LiveScoreProviderClient, ProviderPayloadMapper, RankingsProviderClient
from source.repositories import AuditRepository, MatchRepository
from source.schemas.pydantic.admin import AdminIntegrationItem, AuditLogItem
from source.schemas.pydantic.auth import MessageResponse, SimpleMessage
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.media import MediaFile


class OperationsService:
    def __init__(self) -> None:
        self.storage_dir = Path('var')
        self.media_dir = self.storage_dir / 'media'
        self.media_index_file = self.storage_dir / 'media_index.json'
        self.integrations_file = self.storage_dir / 'integrations.json'
        self.audit_repo = AuditRepository()
        self.matches = MatchRepository()
        self.mapper = ProviderPayloadMapper()

    def _ensure_storage(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

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

    async def get_media(self, media_id: int) -> SuccessResponse[MediaFile]:
        record = next((item for item in self._media_records() if item['id'] == media_id), None)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Media not found')
        return SuccessResponse(data=self._media_item(record))

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

    async def delete_media(self, media_id: int) -> MessageResponse:
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
        return MessageResponse(data=SimpleMessage(message='Media deleted'))

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

    async def list_integrations(self) -> SuccessResponse[list[AdminIntegrationItem]]:
        records = self._integration_records()
        data = [AdminIntegrationItem(provider=provider, status=item.get('status', 'configured'), last_sync_at=datetime.fromisoformat(item['last_sync_at']) if item.get('last_sync_at') else None, last_error=item.get('last_error')) for provider, item in sorted(records.items())]
        return SuccessResponse(data=data)

    async def update_integration(self, provider: str, payload: dict[str, Any]) -> MessageResponse:
        records = self._integration_records()
        current = records.get(provider, {'status': 'configured', 'last_sync_at': None, 'last_error': None, 'settings': {}, 'logs': []})
        normalized_payload = self._normalize_integration_settings(payload)
        updated = current | {'settings': current.get('settings', {}) | normalized_payload}
        records[provider] = updated
        self._save_integration_records(records)
        await self._log_audit(action='integration.update', entity_type='integration', entity_id=None, before_json=current, after_json=updated)
        return MessageResponse(data=SimpleMessage(message=f'Integration {provider} updated'))

    async def sync_integration(self, provider: str, payload: dict[str, Any] | None = None) -> MessageResponse:
        records = self._integration_records()
        current = records.get(provider, {'status': 'configured', 'last_sync_at': None, 'last_error': None, 'settings': {}, 'logs': []})
        payload = payload or {}
        provider_payload = payload.get('provider_payload')
        log_message = 'Manual sync executed'
        try:
            if isinstance(provider_payload, dict):
                if 'live' in provider:
                    events = self.mapper.parse_live_events(provider, provider_payload)
                    applied = await self._apply_live_provider_events(provider, events)
                    log_message = f'Validated {len(events)} live events from provider payload, applied {applied}'
                elif 'rank' in provider:
                    rows = self.mapper.parse_rankings(provider, provider_payload)
                    log_message = f'Validated {len(rows)} ranking rows from provider payload'
            else:
                endpoint = self._validate_integration_endpoint(str(payload.get('endpoint') or current.get('settings', {}).get('endpoint') or ''))
                headers = current.get('settings', {}).get('headers') or {}
                client = self._integration_client(provider, current.get('settings', {}))
                if endpoint and client is not None:
                    if 'live' in provider:
                        events = await client.fetch_events(endpoint, headers=headers)
                        applied = await self._apply_live_provider_events(provider, events)
                        log_message = f'Fetched {len(events)} live events from provider endpoint, applied {applied}'
                    elif 'rank' in provider:
                        rows = await client.fetch_rankings(endpoint, headers=headers)
                        log_message = f'Fetched {len(rows)} ranking rows from provider endpoint'
            log_entry = {'timestamp': datetime.now(tz=UTC).isoformat(), 'message': log_message}
            updated = current | {'status': 'ok', 'last_sync_at': log_entry['timestamp'], 'last_error': None, 'logs': [*current.get('logs', []), log_entry][-20:]}
            records[provider] = updated
            self._save_integration_records(records)
            await self._log_audit(action='integration.sync', entity_type='integration', entity_id=None, before_json=current, after_json=updated)
            return MessageResponse(data=SimpleMessage(message=f'Integration {provider} sync started'))
        except IntegrationSyncError as exc:
            log_entry = {'timestamp': datetime.now(tz=UTC).isoformat(), 'message': f'Provider sync failed: {exc}'}
            updated = current | {'status': 'error', 'last_sync_at': log_entry['timestamp'], 'last_error': str(exc), 'logs': [*current.get('logs', []), log_entry][-20:]}
            records[provider] = updated
            self._save_integration_records(records)
            await self._log_audit(action='integration.sync.failed', entity_type='integration', entity_id=None, before_json=current, after_json=updated)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    async def get_integration_logs(self, provider: str) -> MessageResponse:
        records = self._integration_records()
        current = records.get(provider)
        if current is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Integration not found')
        logs = current.get('logs', [])
        return MessageResponse(data=SimpleMessage(message='\n'.join(item['timestamp'] + ' ' + item['message'] for item in logs) or 'No logs available'))

    async def list_audit_logs(self) -> SuccessResponse[list[AuditLogItem]]:
        async with db_session_manager.session() as session:
            items = await self.audit_repo.list(session)
            return SuccessResponse(data=[AuditLogItem(id=item.id, action=item.action, entity_type=item.entity_type, entity_id=item.entity_id, before_json=item.before_json, after_json=item.after_json, created_at=item.created_at) for item in items])

    async def get_audit_log(self, log_id: int) -> SuccessResponse[AuditLogItem]:
        async with db_session_manager.session() as session:
            item = await self.audit_repo.get(session, log_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Audit log not found')
            return SuccessResponse(data=AuditLogItem(id=item.id, action=item.action, entity_type=item.entity_type, entity_id=item.entity_id, before_json=item.before_json, after_json=item.after_json, created_at=item.created_at))
