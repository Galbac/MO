from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status

from source.config.settings import settings
from source.db.session import db_session_manager
from source.repositories import AuditRepository
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

    def _validate_upload(self, filename: str, content_type: str, size: int) -> None:
        if not filename:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='filename is required')
        if content_type not in settings.media.allowed_content_types:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Unsupported media type')
        if size > settings.media.max_upload_size_bytes:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='File too large')

    async def list_media(self) -> SuccessResponse[list[MediaFile]]:
        return SuccessResponse(data=[self._media_item(item) for item in self._media_records()])

    async def get_media(self, media_id: int) -> SuccessResponse[MediaFile]:
        record = next((item for item in self._media_records() if item['id'] == media_id), None)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Media not found')
        return SuccessResponse(data=self._media_item(record))

    async def upload_media_file(self, file: UploadFile) -> SuccessResponse[MediaFile]:
        filename = (file.filename or '').strip()
        content_type = file.content_type or 'application/octet-stream'
        records = self._media_records()
        media_id = max((item['id'] for item in records), default=0) + 1
        self._ensure_storage()
        file_path = self.media_dir / f'{media_id}_{filename}'
        content = await file.read()
        self._validate_upload(filename, content_type, len(content))
        file_path.write_bytes(content)
        record = {'id': media_id, 'filename': filename, 'content_type': content_type, 'url': f'/static-runtime/media/{file_path.name}', 'size': len(content), 'stored_path': str(file_path), 'created_at': datetime.now(tz=UTC).isoformat()}
        records.append(record)
        self._save_media_records(records)
        await self._log_audit(action='media.upload', entity_type='media', entity_id=media_id, after_json=record)
        return SuccessResponse(data=self._media_item(record))

    async def create_media_record(self, payload: dict[str, Any]) -> SuccessResponse[MediaFile]:
        filename = str(payload.get('filename', '')).strip()
        content_type = str(payload.get('content_type') or 'application/octet-stream')
        raw_content = payload.get('content', '')
        content = raw_content.encode() if isinstance(raw_content, str) else b''
        self._validate_upload(filename, content_type, int(payload.get('size') or len(content)))
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

    async def list_integrations(self) -> SuccessResponse[list[AdminIntegrationItem]]:
        records = self._integration_records()
        data = [AdminIntegrationItem(provider=provider, status=item.get('status', 'configured'), last_sync_at=datetime.fromisoformat(item['last_sync_at']) if item.get('last_sync_at') else None, last_error=item.get('last_error')) for provider, item in sorted(records.items())]
        return SuccessResponse(data=data)

    async def update_integration(self, provider: str, payload: dict[str, Any]) -> MessageResponse:
        records = self._integration_records()
        current = records.get(provider, {'status': 'configured', 'last_sync_at': None, 'last_error': None, 'settings': {}, 'logs': []})
        updated = current | {'settings': current.get('settings', {}) | {key: value for key, value in payload.items() if value not in (None, '')}}
        records[provider] = updated
        self._save_integration_records(records)
        await self._log_audit(action='integration.update', entity_type='integration', entity_id=None, before_json=current, after_json=updated)
        return MessageResponse(data=SimpleMessage(message=f'Integration {provider} updated'))

    async def sync_integration(self, provider: str) -> MessageResponse:
        records = self._integration_records()
        current = records.get(provider, {'status': 'configured', 'last_sync_at': None, 'last_error': None, 'settings': {}, 'logs': []})
        log_entry = {'timestamp': datetime.now(tz=UTC).isoformat(), 'message': 'Manual sync executed'}
        updated = current | {'status': 'ok', 'last_sync_at': log_entry['timestamp'], 'last_error': None, 'logs': [*current.get('logs', []), log_entry][-20:]}
        records[provider] = updated
        self._save_integration_records(records)
        await self._log_audit(action='integration.sync', entity_type='integration', entity_id=None, before_json=current, after_json=updated)
        return MessageResponse(data=SimpleMessage(message=f'Integration {provider} sync started'))

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
