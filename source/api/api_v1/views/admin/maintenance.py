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
        'generate_sitemap': {},
        'rebuild_search_index': {},
        'recalculate_player_stats': {},
    }
    if job_type not in allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Unsupported maintenance job type')
    record = await job_service.enqueue(job_type=job_type, payload=allowed[job_type])
    await job_service.process_due_jobs()
    return SuccessResponse(data=AdminMaintenanceRunResult(job_id=int(record['id']), job_type=job_type))
