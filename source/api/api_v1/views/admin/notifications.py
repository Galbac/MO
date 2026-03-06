from fastapi import APIRouter, Query

from source.schemas.pydantic.admin import (
    AdminNotificationBroadcast,
    AdminNotificationDeliveryLogItem,
    AdminNotificationTemplate,
)
from source.schemas.pydantic.auth import MessageResponse
from source.schemas.pydantic.common import SuccessResponse
from source.services import AdminSupportService

router = APIRouter(prefix="/notifications", tags=["admin-notifications"])
service = AdminSupportService()


@router.get("/templates", response_model=SuccessResponse[list[AdminNotificationTemplate]])
async def get_admin_notification_templates() -> SuccessResponse[list[AdminNotificationTemplate]]:
    return await service.list_notification_templates()


@router.get("", response_model=SuccessResponse[list[AdminNotificationBroadcast]])
async def get_admin_notifications() -> SuccessResponse[list[AdminNotificationBroadcast]]:
    return await service.list_notification_history()


@router.get("/delivery-log", response_model=SuccessResponse[list[AdminNotificationDeliveryLogItem]])
async def get_admin_notification_delivery_log(
    notification_type: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> SuccessResponse[list[AdminNotificationDeliveryLogItem]]:
    return await service.list_notification_delivery_log(
        notification_type=notification_type,
        channel=channel,
        status_value=status,
        limit=limit,
    )


@router.post("/test", response_model=MessageResponse)
async def post_admin_notifications_test() -> MessageResponse:
    return await service.send_test_notification()
