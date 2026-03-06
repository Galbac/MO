from fastapi import APIRouter, Query

from source.schemas.pydantic.admin import (
    AdminIntegrationDetail,
    AdminIntegrationItem,
    AdminIntegrationLogItem,
    AdminIntegrationLogSummary,
    AdminIntegrationSummary,
    AdminIntegrationSyncResult,
    AdminIntegrationUpdateResult,
)
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


@router.get("/summary", response_model=SuccessResponse[AdminIntegrationSummary])
async def get_admin_integrations_summary() -> SuccessResponse[AdminIntegrationSummary]:
    return await service.summarize_integrations()


@router.get("/{provider}", response_model=SuccessResponse[AdminIntegrationDetail])
async def get_admin_integration(provider: str) -> SuccessResponse[AdminIntegrationDetail]:
    return await service.get_integration_detail(provider)


@router.patch("/{provider}", response_model=SuccessResponse[AdminIntegrationUpdateResult])
async def patch_admin_integration(provider: str, payload: dict | None = None) -> SuccessResponse[AdminIntegrationUpdateResult]:
    return await service.update_integration(provider, payload or {})


@router.post("/{provider}/sync", response_model=SuccessResponse[AdminIntegrationSyncResult])
async def sync_admin_integration(provider: str, payload: dict | None = None) -> SuccessResponse[AdminIntegrationSyncResult]:
    return await service.sync_integration(provider, payload or {})


@router.get("/{provider}/logs", response_model=SuccessResponse[list[AdminIntegrationLogItem]])
async def get_admin_integration_logs(
    provider: str,
    level: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> SuccessResponse[list[AdminIntegrationLogItem]]:
    return await service.get_integration_logs(provider, level=level, limit=limit)


@router.get("/{provider}/logs/summary", response_model=SuccessResponse[AdminIntegrationLogSummary])
async def get_admin_integration_logs_summary(provider: str) -> SuccessResponse[AdminIntegrationLogSummary]:
    return await service.summarize_integration_logs(provider)
