from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from source.config.settings import settings
from source.services.cache_service import CacheService
from source.services.runtime_state_store import RuntimeStateStore
from source.services.admin_support_service import AdminSupportService
from source.services.operations_service import OperationsService
from source.services.workflow_service import WorkflowService
from source.tasks.runtime_backup import create_runtime_backup, restore_runtime_backup


class JobService:
    def __init__(self) -> None:
        self.cache = CacheService()
        self.store = RuntimeStateStore()
        self.workflows = WorkflowService()
        self.admin_support = AdminSupportService()
        self.operations = OperationsService()
        self.namespace = 'jobs'

    def _read_jobs(self) -> list[dict[str, Any]]:
        payload = self.store.read_namespace(self.namespace, [])
        return payload if isinstance(payload, list) else []

    def _write_jobs(self, payload: list[dict[str, Any]]) -> None:
        self.store.write_namespace(self.namespace, payload)

    def list_jobs(self) -> list[dict[str, Any]]:
        return self._read_jobs()

    def prune_jobs(self, *, statuses: list[str] | None = None) -> int:
        statuses = statuses or ['finished', 'failed']
        jobs = self._read_jobs()
        kept = [item for item in jobs if item.get('status') not in statuses]
        removed = len(jobs) - len(kept)
        self._write_jobs(kept)
        return removed

    async def retry_failed_job(self, job_id: int) -> dict[str, Any]:
        jobs = self._read_jobs()
        target = next((item for item in jobs if int(item.get('id', 0)) == job_id), None)
        if target is None:
            raise ValueError(f'Job not found: {job_id}')
        target['status'] = 'pending'
        target['error'] = None
        target['updated_at'] = datetime.now(tz=UTC).isoformat()
        self._write_jobs(jobs)
        await self.process_due_jobs()
        return next(item for item in self._read_jobs() if int(item.get('id', 0)) == job_id)

    async def enqueue(self, *, job_type: str, payload: dict[str, Any] | None = None, run_at: datetime | None = None) -> dict[str, Any]:
        jobs = self._read_jobs()
        now = datetime.now(tz=UTC)
        record = {
            'id': max((item.get('id', 0) for item in jobs), default=0) + 1,
            'job_type': job_type,
            'status': 'pending',
            'payload': payload or {},
            'result': None,
            'run_at': (run_at or now).isoformat(),
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'attempts': 0,
            'error': None,
        }
        jobs.append(record)
        self._write_jobs(jobs)
        return record

    async def process_due_jobs(self) -> int:
        if not settings.jobs.enabled:
            return 0
        jobs = self._read_jobs()
        now = datetime.now(tz=UTC)
        processed = 0
        for job in jobs:
            if job.get('status') != 'pending':
                continue
            run_at = datetime.fromisoformat(job['run_at'])
            if run_at > now:
                continue
            job['attempts'] = int(job.get('attempts', 0)) + 1
            job['updated_at'] = now.isoformat()
            try:
                result = await self._run_job(job['job_type'], job.get('payload') or {})
                job['status'] = 'finished'
                job['result'] = result if isinstance(result, dict) else {'value': result} if result is not None else None
                job['error'] = None
                processed += 1
            except Exception as exc:  # noqa: BLE001
                job['status'] = 'failed'
                job['error'] = str(exc)
                job['result'] = None
            job['updated_at'] = datetime.now(tz=UTC).isoformat()
        self._write_jobs(jobs)
        return processed

    async def _run_job(self, job_type: str, payload: dict[str, Any]) -> Any:
        if job_type == 'finalize_match_postprocess':
            await self.workflows.process_finalized_match(int(payload['match_id']))
            return {'match_id': int(payload['match_id']), 'processed': True}
        if job_type == 'publish_scheduled_news':
            news_id = payload.get('news_id')
            published = await self.workflows.publish_due_scheduled_news(int(news_id) if news_id is not None else None)
            return {'news_id': int(news_id) if news_id is not None else None, 'published': published}
        if job_type == 'clear_cache':
            prefixes = payload.get('prefixes') or []
            if prefixes:
                self.cache.invalidate_prefixes(*[str(item) for item in prefixes])
            else:
                self.cache.clear()
            return {'prefixes': [str(item) for item in prefixes], 'cleared_all': not prefixes}
        if job_type == 'generate_sitemap':
            return await self.workflows.generate_sitemap_snapshot(payload.get('base_url'))
        if job_type == 'rebuild_search_index':
            return await self.workflows.rebuild_search_index()
        if job_type == 'recalculate_player_stats':
            player_ids = payload.get('player_ids') or []
            processed = await self.workflows.recalculate_player_aggregates([int(item) for item in player_ids] if player_ids else None)
            return {'player_ids': [int(item) for item in player_ids], 'processed_players': processed}
        if job_type == 'recalculate_h2h':
            recalculated = await self.workflows.recalculate_h2h(int(payload['match_id']))
            return {'match_id': int(payload['match_id']), 'updated': recalculated}
        if job_type == 'generate_draw_snapshot':
            return await self.workflows.generate_tournament_draw_snapshot(int(payload['tournament_id']))
        if job_type == 'import_rankings':
            response = await self.admin_support.import_rankings(payload)
            return {'message': response.data.message}
        if job_type == 'sync_live':
            provider = str(payload.get('provider') or 'live-provider')
            response = await self.operations.sync_integration(provider, payload)
            return {'provider': provider, 'message': response.data.message}
        if job_type == 'backup_runtime':
            archive = create_runtime_backup(destination_path=payload.get('destination_path'), source_dir=payload.get('source_dir'))
            return {'archive_path': str(archive)}
        if job_type == 'restore_runtime':
            restored = restore_runtime_backup(str(payload['archive_path']), target_dir=payload.get('target_dir'))
            return {'restored_path': str(restored)}
        raise ValueError(f'Unsupported job type: {job_type}')

    def backend_name(self) -> str:
        return self.store.backend_name()
