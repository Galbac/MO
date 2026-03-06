from sqlalchemy import text

from fastapi import APIRouter

from source.db.session import db_session_manager
from source.schemas.pydantic.health import HealthResponse, ReadinessDependency, ReadinessResponse
from source.services import JobService, LogService, RuntimeStateStore, WorkflowService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def readiness() -> ReadinessResponse:
    dependencies: dict[str, ReadinessDependency] = {}

    try:
        async with db_session_manager.session() as session:
            await session.execute(text('SELECT 1'))
        dependencies['database'] = ReadinessDependency(status='ok', detail='reachable')
    except Exception as exc:  # noqa: BLE001
        dependencies['database'] = ReadinessDependency(status='error', detail=str(exc))

    store = RuntimeStateStore()
    dependencies['runtime_state'] = ReadinessDependency(status='ok', backend=store.backend_name(), detail='ready')

    jobs = JobService()
    job_items = jobs.list_jobs()
    pending_jobs = sum(1 for item in job_items if str(item.get('status')) == 'pending')
    failed_jobs = sum(1 for item in job_items if str(item.get('status')) == 'failed')
    job_status = 'ok' if failed_jobs == 0 else 'degraded'
    dependencies['job_queue'] = ReadinessDependency(status=job_status, backend=jobs.backend_name(), detail=f'pending={pending_jobs}, failed={failed_jobs}')

    workflow_service = WorkflowService()
    artifacts = workflow_service.maintenance_artifacts()
    existing_artifacts = sum(1 for item in artifacts if bool(item.get('exists')))
    dependencies['maintenance'] = ReadinessDependency(status='ok', detail=f'artifacts={existing_artifacts}/{len(artifacts)}')

    logs = LogService()
    dependencies['logging'] = ReadinessDependency(status='ok', backend='jsonl', detail=f'categories={len(logs.categories())}')

    overall = 'ok' if all(item.status == 'ok' for item in dependencies.values()) else 'degraded'
    return ReadinessResponse(status=overall, dependencies=dependencies)
