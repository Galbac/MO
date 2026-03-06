from fastapi import APIRouter

from source.schemas.pydantic.admin import AuditLogItem
from source.schemas.pydantic.common import SuccessResponse
from source.services import OperationsService

router = APIRouter(prefix="/audit-logs", tags=["admin-audit"])
service = OperationsService()


@router.get("", response_model=SuccessResponse[list[AuditLogItem]])
async def list_audit_logs(
    user_id: int | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> SuccessResponse[list[AuditLogItem]]:
    return await service.list_audit_logs(
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{log_id}", response_model=SuccessResponse[AuditLogItem])
async def get_audit_log(log_id: int) -> SuccessResponse[AuditLogItem]:
    return await service.get_audit_log(log_id)
