from fastapi import APIRouter, HTTPException, status

from source.schemas.pydantic.admin import AdminJobItem, AdminJobPruneResult
from source.schemas.pydantic.auth import MessageResponse, SimpleMessage
from source.schemas.pydantic.common import SuccessResponse
from source.services import JobService

router = APIRouter(prefix="/jobs", tags=["admin-jobs"])
service = JobService()


@router.get("", response_model=SuccessResponse[list[AdminJobItem]])
async def list_admin_jobs() -> SuccessResponse[list[AdminJobItem]]:
    return SuccessResponse(data=[AdminJobItem.model_validate(item) for item in service.list_jobs()])


@router.post("/{job_id}/retry", response_model=SuccessResponse[AdminJobItem])
async def retry_admin_job(job_id: int) -> SuccessResponse[AdminJobItem]:
    try:
        item = await service.retry_failed_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SuccessResponse(data=AdminJobItem.model_validate(item))


@router.post("/prune", response_model=SuccessResponse[AdminJobPruneResult])
async def prune_admin_jobs(payload: dict | None = None) -> SuccessResponse[AdminJobPruneResult]:
    statuses = payload.get('statuses') if isinstance(payload, dict) else None
    removed = service.prune_jobs(statuses=[str(item) for item in statuses] if statuses else None)
    return SuccessResponse(data=AdminJobPruneResult(removed=removed))


@router.post("/process", response_model=MessageResponse)
async def process_admin_jobs() -> MessageResponse:
    processed = await service.process_due_jobs()
    return MessageResponse(data=SimpleMessage(message=f'Processed {processed} jobs'))
