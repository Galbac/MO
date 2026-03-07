from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from source.schemas.pydantic.admin import AdminJobItem, AdminJobProcessResult, AdminJobPruneResult, AdminJobSummary
from source.schemas.pydantic.common import SuccessResponse
from source.services import JobService

router = APIRouter(prefix="/jobs", tags=["admin-jobs"])
service = JobService()


@router.get("", response_model=SuccessResponse[list[AdminJobItem]])
async def list_admin_jobs(
    status: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> SuccessResponse[list[AdminJobItem]]:
    return SuccessResponse(data=[AdminJobItem.model_validate(item) for item in service.filtered_jobs(status=status, job_type=job_type, limit=limit)])


@router.get("/summary", response_model=SuccessResponse[AdminJobSummary])
async def get_admin_jobs_summary() -> SuccessResponse[AdminJobSummary]:
    payload = service.summary()
    latest_updated_at = payload.get('latest_updated_at')
    if isinstance(latest_updated_at, str):
        payload['latest_updated_at'] = datetime.fromisoformat(latest_updated_at)
    return SuccessResponse(data=AdminJobSummary.model_validate(payload))


@router.post("/prune", response_model=SuccessResponse[AdminJobPruneResult])
async def prune_admin_jobs(payload: dict | None = None) -> SuccessResponse[AdminJobPruneResult]:
    statuses = payload.get('statuses') if isinstance(payload, dict) else None
    result = service.prune_jobs(statuses=[str(item) for item in statuses] if statuses else None)
    return SuccessResponse(data=AdminJobPruneResult.model_validate(result))


@router.post("/process", response_model=SuccessResponse[AdminJobProcessResult])
async def process_admin_jobs() -> SuccessResponse[AdminJobProcessResult]:
    result = await service.process_due_jobs()
    return SuccessResponse(data=AdminJobProcessResult.model_validate(result))


@router.get("/{job_id}", response_model=SuccessResponse[AdminJobItem])
async def get_admin_job(job_id: int) -> SuccessResponse[AdminJobItem]:
    item = service.get_job(job_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Job not found: {job_id}')
    return SuccessResponse(data=AdminJobItem.model_validate(item))


@router.post("/{job_id}/cancel", response_model=SuccessResponse[AdminJobItem])
async def cancel_admin_job(job_id: int) -> SuccessResponse[AdminJobItem]:
    try:
        item = await service.cancel_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return SuccessResponse(data=AdminJobItem.model_validate(item))


@router.post("/{job_id}/retry", response_model=SuccessResponse[AdminJobItem])
async def retry_admin_job(job_id: int) -> SuccessResponse[AdminJobItem]:
    try:
        item = await service.retry_failed_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SuccessResponse(data=AdminJobItem.model_validate(item))
