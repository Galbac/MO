from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from source.config.settings import settings
from source.db.session import db_session_manager
from source.integrations import ProviderPayloadMapper
from source.repositories import AdminSupportRepository
from source.schemas.pydantic.admin import (
    AdminActionResult,
    AdminNotificationBroadcast,
    AdminNotificationDeliveryLogItem,
    AdminNotificationTemplate,
    AdminSettingsPayload,
)
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.news import NewsCategoryItem, TagItem
from source.schemas.pydantic.ranking import RankingImportJob, RankingImportResult, RankingRecalculationResult
from source.services.cache_service import CacheService
from source.services.workflow_service import WorkflowService


class AdminSupportService:
    def __init__(self) -> None:
        self.repo = AdminSupportRepository()
        self.storage_dir = Path('var')
        self.cache = CacheService()
        self.mapper = ProviderPayloadMapper()
        self.workflows = WorkflowService()
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

    def _delivery_logs(self) -> list[dict[str, Any]]:
        path = Path(settings.notifications.delivery_log_path)
        if not path.exists():
            return []
        return json.loads(path.read_text())

    @staticmethod
    def _delivery_stats(entries: list[dict[str, Any]]) -> dict[str, int]:
        stats = {'sent': 0, 'queued': 0, 'suppressed': 0, 'skipped': 0}
        for entry in entries:
            status_value = str(entry.get('status') or '')
            if status_value in stats:
                stats[status_value] += 1
        stats['total'] = sum(stats.values())
        return stats

    @staticmethod
    def _action_result(
        *,
        entity_type: str,
        action: str,
        entity_id: int | None = None,
        message: str | None = None,
        status: str = 'ok',
        details: dict[str, Any] | None = None,
    ) -> SuccessResponse[AdminActionResult]:
        return SuccessResponse(
            data=AdminActionResult(
                entity_type=entity_type,
                action=action,
                status=status,
                entity_id=entity_id,
                message=message,
                details=details or {},
            )
        )

    async def get_settings(self) -> SuccessResponse[dict]:
        payload = self._read_json(self.settings_file)
        updated_at = None
        if self.settings_file.exists():
            updated_at = datetime.fromtimestamp(self.settings_file.stat().st_mtime, tz=UTC)
        return SuccessResponse(
            data=AdminSettingsPayload(
                values=payload or {},
                storage_backend='local_file',
                storage_path=str(self.settings_file),
                updated_at=updated_at,
            ).model_dump()
        )

    async def update_settings(self, payload: dict[str, Any]) -> SuccessResponse[dict]:
        current = self._read_json(self.settings_file) or {}
        merged = current | {key: value for key, value in payload.items() if value not in (None, '')}
        self._write_json(self.settings_file, merged)
        self._invalidate_cache('news:', 'rankings:', 'players:', 'tournaments:', 'matches:', 'live:', 'search:')
        updated_at = datetime.fromtimestamp(self.settings_file.stat().st_mtime, tz=UTC) if self.settings_file.exists() else None
        return SuccessResponse(
            data=AdminSettingsPayload(
                values=merged,
                storage_backend='local_file',
                storage_path=str(self.settings_file),
                updated_at=updated_at,
            ).model_dump()
        )

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
            delivery_logs = self._delivery_logs()
            data = []
            for index, ((code, title), items) in enumerate(sorted(grouped.items(), key=lambda value: max(item.created_at for item in value[1]), reverse=True), start=1):
                latest = max(items, key=lambda item: item.created_at)
                matching_logs = [entry for entry in delivery_logs if entry.get('notification_type') == code and entry.get('title') == title]
                sent_count = len([entry for entry in matching_logs if entry.get('status') in {'sent', 'queued'}]) or len(items)
                status_value = matching_logs[-1]['status'] if matching_logs else ('sent' if all(item.status == 'read' for item in items) else 'queued')
                data.append(
                    AdminNotificationBroadcast(
                        id=index,
                        code=code,
                        title=title,
                        status=status_value,
                        sent_count=sent_count,
                        created_at=latest.created_at,
                        last_delivery_at=datetime.fromisoformat(matching_logs[-1]['created_at']) if matching_logs and matching_logs[-1].get('created_at') else None,
                        last_reason=str(matching_logs[-1].get('reason')) if matching_logs and matching_logs[-1].get('reason') else None,
                        channels=sorted({str(entry.get('channel') or 'web') for entry in matching_logs}) or ['web'],
                        delivery_stats=self._delivery_stats(matching_logs),
                    )
                )
            return SuccessResponse(data=data)

    async def list_notification_delivery_log(
        self,
        *,
        notification_type: str | None = None,
        channel: str | None = None,
        status_value: str | None = None,
        limit: int = 100,
    ) -> SuccessResponse[list[AdminNotificationDeliveryLogItem]]:
        items = self._delivery_logs()
        filtered = []
        for entry in reversed(items):
            if notification_type and entry.get('notification_type') != notification_type:
                continue
            if channel and entry.get('channel') != channel:
                continue
            if status_value and entry.get('status') != status_value:
                continue
            if not entry.get('created_at'):
                continue
            filtered.append(
                AdminNotificationDeliveryLogItem(
                    user_id=int(entry.get('user_id') or 0),
                    channel=str(entry.get('channel') or 'web'),
                    notification_type=str(entry.get('notification_type') or ''),
                    title=str(entry.get('title') or ''),
                    entity_type=str(entry.get('entity_type') or ''),
                    entity_id=int(entry.get('entity_id') or 0),
                    status=str(entry.get('status') or ''),
                    reason=str(entry.get('reason')) if entry.get('reason') is not None else None,
                    created_at=datetime.fromisoformat(str(entry['created_at'])),
                )
            )
            if len(filtered) >= max(1, min(limit, 500)):
                break
        return SuccessResponse(data=filtered)

    async def send_test_notification(self) -> SuccessResponse[AdminActionResult]:
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
            created = await self.repo.create_notification(session, payload)
            return self._action_result(
                entity_type='notification',
                action='test.send',
                entity_id=created.id,
                message='Test notification sent',
                details={'user_id': user.id, 'notification_type': payload['type']},
            )

    async def list_categories(self) -> SuccessResponse[list[NewsCategoryItem]]:
        async with db_session_manager.session() as session:
            items = await self.repo.list_categories(session)
            return SuccessResponse(data=[NewsCategoryItem(id=item.id, slug=item.slug, name=item.name) for item in items])

    async def create_category(self, payload: dict[str, Any]) -> SuccessResponse[AdminActionResult]:
        async with db_session_manager.session() as session:
            item = await self.repo.create_category(session, {'name': self._require(payload, 'name'), 'slug': self._require(payload, 'slug')})
            self._invalidate_cache('news:', 'search:')
            return self._action_result(entity_type='news_category', action='create', entity_id=item.id, message='News category created', details={'slug': item.slug, 'name': item.name})

    async def update_category(self, category_id: int, payload: dict[str, Any]) -> SuccessResponse[AdminActionResult]:
        async with db_session_manager.session() as session:
            item = await self.repo.get_category(session, category_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category not found')
            updated = await self.repo.update_category(session, item, {'name': self._require(payload | {'name': payload.get('name', item.name)}, 'name'), 'slug': self._require(payload | {'slug': payload.get('slug', item.slug)}, 'slug')})
            self._invalidate_cache('news:', 'search:')
            return self._action_result(entity_type='news_category', action='update', entity_id=category_id, message='News category updated', details={'slug': updated.slug, 'name': updated.name})

    async def delete_category(self, category_id: int) -> SuccessResponse[AdminActionResult]:
        async with db_session_manager.session() as session:
            item = await self.repo.get_category(session, category_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category not found')
            details = {'slug': item.slug, 'name': item.name}
            await self.repo.delete_category(session, item)
            self._invalidate_cache('news:', 'search:')
            return self._action_result(entity_type='news_category', action='delete', entity_id=category_id, message='News category deleted', details=details)

    async def list_tags(self) -> SuccessResponse[list[TagItem]]:
        async with db_session_manager.session() as session:
            items = await self.repo.list_tags(session)
            return SuccessResponse(data=[TagItem(id=item.id, slug=item.slug, name=item.name) for item in items])

    async def create_tag(self, payload: dict[str, Any]) -> SuccessResponse[AdminActionResult]:
        async with db_session_manager.session() as session:
            item = await self.repo.create_tag(session, {'name': self._require(payload, 'name'), 'slug': self._require(payload, 'slug')})
            self._invalidate_cache('news:', 'search:')
            return self._action_result(entity_type='tag', action='create', entity_id=item.id, message='Tag created', details={'slug': item.slug, 'name': item.name})

    async def update_tag(self, tag_id: int, payload: dict[str, Any]) -> SuccessResponse[AdminActionResult]:
        async with db_session_manager.session() as session:
            item = await self.repo.get_tag(session, tag_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tag not found')
            updated = await self.repo.update_tag(session, item, {'name': self._require(payload | {'name': payload.get('name', item.name)}, 'name'), 'slug': self._require(payload | {'slug': payload.get('slug', item.slug)}, 'slug')})
            self._invalidate_cache('news:', 'search:')
            return self._action_result(entity_type='tag', action='update', entity_id=tag_id, message='Tag updated', details={'slug': updated.slug, 'name': updated.name})

    async def delete_tag(self, tag_id: int) -> SuccessResponse[AdminActionResult]:
        async with db_session_manager.session() as session:
            item = await self.repo.get_tag(session, tag_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tag not found')
            details = {'slug': item.slug, 'name': item.name}
            await self.repo.delete_tag(session, item)
            self._invalidate_cache('news:', 'search:')
            return self._action_result(entity_type='tag', action='delete', entity_id=tag_id, message='Tag deleted', details=details)

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

    async def import_rankings(self, payload: dict[str, Any]) -> SuccessResponse[RankingImportResult]:
        provider = str(payload.get('provider') or '').strip()
        provider_payload = payload.get('provider_payload')
        if provider and isinstance(provider_payload, dict):
            rows = self.mapper.parse_rankings(provider, provider_payload)
            names = [row.player_name for row in rows]
            async with db_session_manager.session() as session:
                players = {item.full_name: item for item in await self.repo.find_players_by_names(session, names)}
                if len(players) != len(set(names)):
                    missing = sorted(set(names) - set(players))
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'Players not found for rankings import: {", ".join(missing)}')
                existing_snapshots = [item for item in await self.repo.list_ranking_snapshots(session) if item.ranking_type == rows[0].ranking_type]
                latest_existing_date = max((item.ranking_date for item in existing_snapshots), default=None)
                previous = {item.player_id: item for item in await self.repo.get_previous_rankings(session, rows[0].ranking_type, rows[0].ranking_date)}
                ranking_rows: list[dict[str, Any]] = []
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
                await self.repo.replace_rankings(session, ranking_type=rows[0].ranking_type, ranking_date=rows[0].ranking_date, rows=ranking_rows)
                if latest_existing_date is None or rows[0].ranking_date >= latest_existing_date:
                    affected_player_ids = [item.player_id for item in existing_snapshots]
                    await self.repo.clear_player_current_rankings(session, sorted(set(affected_player_ids) - {row['player_id'] for row in ranking_rows}))
                    await self.repo.apply_player_current_rankings(session, ranking_rows)
                await self.repo.commit(session)
            await self.workflows.process_ranking_updates(ranking_rows, ranking_type=rows[0].ranking_type, ranking_date=rows[0].ranking_date)
            jobs = self._read_json(self.jobs_file) or []
            imported_at = datetime.now(tz=UTC).isoformat()
            jobs.append({'ranking_type': rows[0].ranking_type, 'status': 'finished', 'imported_at': imported_at, 'processed_rows': len(ranking_rows), 'source_file': str(payload.get('source_file') or provider)})
            self._write_json(self.jobs_file, jobs)
            self._invalidate_cache('rankings:', 'players:', 'search:')
            return SuccessResponse(
                data=RankingImportResult(
                    ranking_type=rows[0].ranking_type,
                    status='finished',
                    imported_at=imported_at,
                    processed_rows=len(ranking_rows),
                    source=str(payload.get('source_file') or provider),
                    mode='provider_payload',
                )
            )

        async with db_session_manager.session() as session:
            ranking_type = await self.repo.get_latest_ranking_type(session) or 'unknown'
        jobs = self._read_json(self.jobs_file) or []
        imported_at = datetime.now(tz=UTC).isoformat()
        resolved_ranking_type = str(payload.get('ranking_type') or ranking_type)
        resolved_source = str(payload.get('source_file') or '')
        jobs.append({'ranking_type': resolved_ranking_type, 'status': 'queued', 'imported_at': imported_at, 'processed_rows': 0, 'source_file': resolved_source})
        self._write_json(self.jobs_file, jobs)
        self._invalidate_cache('rankings:', 'players:')
        return SuccessResponse(
            data=RankingImportResult(
                ranking_type=resolved_ranking_type,
                status='queued',
                imported_at=imported_at,
                processed_rows=0,
                source=resolved_source or None,
                mode='queued',
            )
        )

    async def recalculate_ranking_movements(self) -> SuccessResponse[RankingRecalculationResult]:
        async with db_session_manager.session() as session:
            ranking_types = await self.repo.list_ranking_types(session)
            snapshot_dates_processed = 0
            updated_rows = 0
            for ranking_type in ranking_types:
                previous_positions: dict[int, int] = {}
                for ranking_date in await self.repo.list_ranking_dates(session, ranking_type):
                    snapshot_dates_processed += 1
                    snapshots = await self.repo.list_rankings_for_date(session, ranking_type, ranking_date)
                    current_positions: dict[int, int] = {}
                    for snapshot in snapshots:
                        current_positions[snapshot.player_id] = int(snapshot.rank_position)
                        snapshot.movement = 0 if snapshot.player_id not in previous_positions else previous_positions[snapshot.player_id] - int(snapshot.rank_position)
                        updated_rows += 1
                    previous_positions = current_positions
            await self.repo.commit(session)
        self._invalidate_cache('rankings:', 'players:')
        return SuccessResponse(
            data=RankingRecalculationResult(
                message='Ranking movements recalculated',
                ranking_types=[str(item) for item in ranking_types],
                snapshot_dates_processed=snapshot_dates_processed,
                updated_rows=updated_rows,
            )
        )
