from fastapi import APIRouter

from source.schemas.pydantic.admin import AuditLogItem
from source.schemas.pydantic.common import SuccessResponse
from source.services import OperationsService

router = APIRouter(prefix="/audit-logs", tags=["admin-audit"])
service = OperationsService()


@router.get("", response_model=SuccessResponse[list[AuditLogItem]])
async def list_audit_logs() -> SuccessResponse[list[AuditLogItem]]:
    return await service.list_audit_logs()


@router.get("/{log_id}", response_model=SuccessResponse[AuditLogItem])
async def get_audit_log(log_id: int) -> SuccessResponse[AuditLogItem]:
    return await service.get_audit_log(log_id)
