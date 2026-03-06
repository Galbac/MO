from fastapi import APIRouter

from source.schemas.pydantic.admin import AdminIntegrationItem
from source.schemas.pydantic.auth import MessageResponse
from source.schemas.pydantic.common import SuccessResponse
from source.services import OperationsService

router = APIRouter(prefix="/integrations", tags=["admin-integrations"])
service = OperationsService()


@router.get("", response_model=SuccessResponse[list[AdminIntegrationItem]])
async def get_admin_integrations() -> SuccessResponse[list[AdminIntegrationItem]]:
    return await service.list_integrations()


@router.patch("/{provider}", response_model=MessageResponse)
async def patch_admin_integration(provider: str, payload: dict | None = None) -> MessageResponse:
    return await service.update_integration(provider, payload or {})


@router.post("/{provider}/sync", response_model=MessageResponse)
async def sync_admin_integration(provider: str) -> MessageResponse:
    return await service.sync_integration(provider)


@router.get("/{provider}/logs", response_model=MessageResponse)
async def get_admin_integration_logs(provider: str) -> MessageResponse:
    return await service.get_integration_logs(provider)
