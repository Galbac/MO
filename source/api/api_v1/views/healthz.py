from sqlalchemy import text

from fastapi import APIRouter

from source.db.session import db_session_manager
from source.schemas.pydantic.health import HealthResponse, ReadinessDependency, ReadinessResponse
from source.services import RuntimeStateStore

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

    overall = 'ok' if all(item.status == 'ok' for item in dependencies.values()) else 'degraded'
    return ReadinessResponse(status=overall, dependencies=dependencies)
