from fastapi import APIRouter, Query

from source.schemas.pydantic.admin import AdminIntegrationItem, AdminIntegrationLogItem
from source.schemas.pydantic.auth import MessageResponse
from source.schemas.pydantic.common import SuccessResponse
from source.services import OperationsService

router = APIRouter(prefix="/integrations", tags=["admin-integrations"])
service = OperationsService()


@router.get("", response_model=SuccessResponse[list[AdminIntegrationItem]])
async def get_admin_integrations(
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> SuccessResponse[list[AdminIntegrationItem]]:
    return await service.list_integrations(provider=provider, status=status)


@router.patch("/{provider}", response_model=MessageResponse)
async def patch_admin_integration(provider: str, payload: dict | None = None) -> MessageResponse:
    return await service.update_integration(provider, payload or {})


@router.post("/{provider}/sync", response_model=MessageResponse)
async def sync_admin_integration(provider: str, payload: dict | None = None) -> MessageResponse:
    return await service.sync_integration(provider, payload or {})


@router.get("/{provider}/logs", response_model=SuccessResponse[list[AdminIntegrationLogItem]])
async def get_admin_integration_logs(provider: str) -> SuccessResponse[list[AdminIntegrationLogItem]]:
    return await service.get_integration_logs(provider)
