from fastapi import APIRouter

from source.schemas.pydantic.admin import AdminSettingsPayload
from source.schemas.pydantic.common import SuccessResponse
from source.services import AdminSupportService

router = APIRouter(prefix="/settings", tags=["admin-settings"])
service = AdminSupportService()


@router.get("", response_model=SuccessResponse[AdminSettingsPayload])
async def get_admin_settings() -> SuccessResponse[AdminSettingsPayload]:
    return await service.get_settings()


@router.patch("", response_model=SuccessResponse[AdminSettingsPayload])
async def patch_admin_settings(payload: dict) -> SuccessResponse[AdminSettingsPayload]:
    return await service.update_settings(payload)
