from fastapi import APIRouter, HTTPException, status

from source.schemas.pydantic.admin import AdminMaintenanceArtifact, AdminMaintenanceRunResult
from source.schemas.pydantic.common import SuccessResponse
from source.services import JobService, WorkflowService

router = APIRouter(prefix="/maintenance", tags=["admin-maintenance"])
job_service = JobService()
workflow_service = WorkflowService()


@router.get("", response_model=SuccessResponse[list[AdminMaintenanceArtifact]])
async def list_maintenance_artifacts() -> SuccessResponse[list[AdminMaintenanceArtifact]]:
    return SuccessResponse(
        data=[
            AdminMaintenanceArtifact.model_validate(item)
            for item in workflow_service.maintenance_artifacts()
        ]
    )


@router.post("/run", response_model=SuccessResponse[AdminMaintenanceRunResult])
async def run_maintenance_job(payload: dict | None = None) -> SuccessResponse[AdminMaintenanceRunResult]:
    payload = payload or {}
    job_type = str(payload.get('job_type') or '').strip()
    allowed = {
        'generate_sitemap': lambda data: {'base_url': str(data.get('base_url') or '').strip() or None},
        'rebuild_search_index': lambda data: {},
        'recalculate_player_stats': lambda data: {'player_ids': [int(item) for item in list(data.get('player_ids') or [])]},
        'recalculate_h2h': lambda data: {'match_id': int(data['match_id'])},
        'generate_draw_snapshot': lambda data: {'tournament_id': int(data['tournament_id'])},
        'clear_cache': lambda data: {'prefixes': [str(item) for item in list(data.get('prefixes') or [])]},
        'publish_scheduled_news': lambda data: {'news_id': int(data['news_id'])} if data.get('news_id') not in (None, '') else {},
        'sync_live': lambda data: {'provider': str(data.get('provider') or 'live-provider'), **({'provider_payload': data['provider_payload']} if isinstance(data.get('provider_payload'), dict) else {})},
        'import_rankings': lambda data: dict(data),
        'backup_runtime': lambda data: {'destination_path': str(data.get('destination_path') or '').strip() or None, 'source_dir': str(data.get('source_dir') or '').strip() or None},
        'restore_runtime': lambda data: {'archive_path': str(data['archive_path']), 'target_dir': str(data.get('target_dir') or '.').strip() or '.'},
    }
    if job_type not in allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Unsupported maintenance job type')
    try:
        job_payload = allowed[job_type](payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'Invalid payload for maintenance job: {job_type}') from exc
    record = await job_service.enqueue(job_type=job_type, payload=job_payload)
    await job_service.process_due_jobs()
    return SuccessResponse(data=AdminMaintenanceRunResult(job_id=int(record['id']), job_type=job_type))
