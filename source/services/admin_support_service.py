from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from source.db.session import db_session_manager
from source.repositories import AdminSupportRepository
from source.schemas.pydantic.admin import AdminNotificationBroadcast, AdminNotificationTemplate
from source.schemas.pydantic.auth import MessageResponse, SimpleMessage
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.news import NewsCategoryItem, TagItem
from source.schemas.pydantic.ranking import RankingImportJob
from source.services.cache_service import CacheService


class AdminSupportService:
    def __init__(self) -> None:
        self.repo = AdminSupportRepository()
        self.storage_dir = Path('var')
        self.cache = CacheService()
        self.settings_file = self.storage_dir / 'admin_settings.json'
        self.jobs_file = self.storage_dir / 'ranking_import_jobs.json'

    @staticmethod
    def _require(payload: dict[str, Any], field: str) -> str:
        value = str(payload.get(field, '')).strip()
        if not value:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'{field} is required')
        return value

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def _write_json(self, path: Path, payload: Any) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))

    def _invalidate_cache(self, *prefixes: str) -> None:
        self.cache.invalidate_prefixes(*prefixes)

    async def get_settings(self) -> SuccessResponse[dict]:
        payload = self._read_json(self.settings_file)
        return SuccessResponse(data=payload or {})

    async def update_settings(self, payload: dict[str, Any]) -> SuccessResponse[dict]:
        current = self._read_json(self.settings_file) or {}
        merged = current | {key: value for key, value in payload.items() if value not in (None, '')}
        self._write_json(self.settings_file, merged)
        self._invalidate_cache('news:', 'rankings:', 'players:', 'tournaments:', 'matches:', 'live:', 'search:')
        return SuccessResponse(data=merged)

    async def list_notification_templates(self) -> SuccessResponse[list[AdminNotificationTemplate]]:
        async with db_session_manager.session() as session:
            notifications = await self.repo.list_notifications(session)
            grouped: dict[str, Any] = {}
            for item in notifications:
                bucket = grouped.get(item.type)
                if bucket is None or item.created_at > bucket.created_at:
                    grouped[item.type] = item
            data = [AdminNotificationTemplate(id=item.id, code=item.type, title=item.title, channel='web', is_active=True, updated_at=item.created_at) for item in grouped.values()]
            data.sort(key=lambda item: item.code)
            return SuccessResponse(data=data)

    async def list_notification_history(self) -> SuccessResponse[list[AdminNotificationBroadcast]]:
        async with db_session_manager.session() as session:
            notifications = await self.repo.list_notifications(session)
            grouped: dict[tuple[str, str], list[Any]] = {}
            for item in notifications:
                grouped.setdefault((item.type, item.title), []).append(item)
            data = []
            for index, ((_, title), items) in enumerate(sorted(grouped.items(), key=lambda value: max(item.created_at for item in value[1]), reverse=True), start=1):
                latest = max(items, key=lambda item: item.created_at)
                status_value = 'sent' if all(item.status == 'read' for item in items) else 'queued'
                data.append(AdminNotificationBroadcast(id=index, title=title, status=status_value, sent_count=len(items), created_at=latest.created_at))
            return SuccessResponse(data=data)

    async def send_test_notification(self) -> MessageResponse:
        async with db_session_manager.session() as session:
            user = await self.repo.get_first_active_user(session)
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Active user not found')
            notifications = await self.repo.list_notifications(session)
            latest = notifications[0] if notifications else None
            payload = {
                'user_id': user.id,
                'type': latest.type if latest else 'system',
                'title': latest.title if latest else 'Notification',
                'body': latest.body if latest else 'Notification queued.',
                'payload_json': {'source': 'admin-test'},
                'status': 'unread',
                'read_at': None,
            }
            await self.repo.create_notification(session, payload)
            return MessageResponse(data=SimpleMessage(message='Test notification sent'))

    async def list_categories(self) -> SuccessResponse[list[NewsCategoryItem]]:
        async with db_session_manager.session() as session:
            items = await self.repo.list_categories(session)
            return SuccessResponse(data=[NewsCategoryItem(id=item.id, slug=item.slug, name=item.name) for item in items])

    async def create_category(self, payload: dict[str, Any]) -> MessageResponse:
        async with db_session_manager.session() as session:
            await self.repo.create_category(session, {'name': self._require(payload, 'name'), 'slug': self._require(payload, 'slug')})
            self._invalidate_cache('news:', 'search:')
            return MessageResponse(data=SimpleMessage(message='News category created'))

    async def update_category(self, category_id: int, payload: dict[str, Any]) -> MessageResponse:
        async with db_session_manager.session() as session:
            item = await self.repo.get_category(session, category_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category not found')
            await self.repo.update_category(session, item, {'name': self._require(payload | {'name': payload.get('name', item.name)}, 'name'), 'slug': self._require(payload | {'slug': payload.get('slug', item.slug)}, 'slug')})
            self._invalidate_cache('news:', 'search:')
            return MessageResponse(data=SimpleMessage(message='News category updated'))

    async def delete_category(self, category_id: int) -> MessageResponse:
        async with db_session_manager.session() as session:
            item = await self.repo.get_category(session, category_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category not found')
            await self.repo.delete_category(session, item)
            self._invalidate_cache('news:', 'search:')
            return MessageResponse(data=SimpleMessage(message='News category deleted'))

    async def list_tags(self) -> SuccessResponse[list[TagItem]]:
        async with db_session_manager.session() as session:
            items = await self.repo.list_tags(session)
            return SuccessResponse(data=[TagItem(id=item.id, slug=item.slug, name=item.name) for item in items])

    async def create_tag(self, payload: dict[str, Any]) -> MessageResponse:
        async with db_session_manager.session() as session:
            await self.repo.create_tag(session, {'name': self._require(payload, 'name'), 'slug': self._require(payload, 'slug')})
            self._invalidate_cache('news:', 'search:')
            return MessageResponse(data=SimpleMessage(message='Tag created'))

    async def update_tag(self, tag_id: int, payload: dict[str, Any]) -> MessageResponse:
        async with db_session_manager.session() as session:
            item = await self.repo.get_tag(session, tag_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tag not found')
            await self.repo.update_tag(session, item, {'name': self._require(payload | {'name': payload.get('name', item.name)}, 'name'), 'slug': self._require(payload | {'slug': payload.get('slug', item.slug)}, 'slug')})
            self._invalidate_cache('news:', 'search:')
            return MessageResponse(data=SimpleMessage(message='Tag updated'))

    async def delete_tag(self, tag_id: int) -> MessageResponse:
        async with db_session_manager.session() as session:
            item = await self.repo.get_tag(session, tag_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tag not found')
            await self.repo.delete_tag(session, item)
            self._invalidate_cache('news:', 'search:')
            return MessageResponse(data=SimpleMessage(message='Tag deleted'))

    async def list_ranking_jobs(self) -> SuccessResponse[list[RankingImportJob]]:
        async with db_session_manager.session() as session:
            snapshots = await self.repo.list_ranking_snapshots(session)
        grouped: dict[tuple[str, str], int] = {}
        for item in snapshots:
            grouped[(item.ranking_type, item.ranking_date)] = grouped.get((item.ranking_type, item.ranking_date), 0) + 1
        stored = self._read_json(self.jobs_file) or []
        data = [RankingImportJob(id=index + 1, ranking_type=ranking_type, status='finished', imported_at=f'{ranking_date}T00:00:00+00:00', processed_rows=rows) for index, ((ranking_type, ranking_date), rows) in enumerate(sorted(grouped.items(), key=lambda item: item[0][1], reverse=True))]
        next_id = len(data) + 1
        for entry in stored:
            data.append(RankingImportJob(id=next_id, ranking_type=entry['ranking_type'], status=entry['status'], imported_at=entry['imported_at'], processed_rows=entry['processed_rows']))
            next_id += 1
        return SuccessResponse(data=data)

    async def import_rankings(self, payload: dict[str, Any]) -> MessageResponse:
        async with db_session_manager.session() as session:
            ranking_type = await self.repo.get_latest_ranking_type(session) or 'unknown'
        jobs = self._read_json(self.jobs_file) or []
        jobs.append({'ranking_type': str(payload.get('ranking_type') or ranking_type), 'status': 'queued', 'imported_at': datetime.now(tz=UTC).isoformat(), 'processed_rows': 0, 'source_file': str(payload.get('source_file') or '')})
        self._write_json(self.jobs_file, jobs)
        self._invalidate_cache('rankings:', 'players:')
        return MessageResponse(data=SimpleMessage(message='Ranking import queued'))

    async def recalculate_ranking_movements(self) -> MessageResponse:
        self._invalidate_cache('rankings:', 'players:')
        return MessageResponse(data=SimpleMessage(message='Ranking movement recalculation queued'))
