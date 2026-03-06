from fastapi import APIRouter, Depends, Request

from source.api.dependencies.auth import require_authenticated_user
from source.schemas.pydantic.auth import MessageResponse
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.notification import NotificationItem, NotificationUnreadCount
from source.services import UserEngagementService

router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(require_authenticated_user)])
service = UserEngagementService()


@router.get("", response_model=SuccessResponse[list[NotificationItem]])
async def get_notifications(request: Request) -> SuccessResponse[list[NotificationItem]]:
    return await service.list_notifications(request)


@router.get("/unread-count", response_model=SuccessResponse[NotificationUnreadCount])
async def get_unread_count(request: Request) -> SuccessResponse[NotificationUnreadCount]:
    return await service.get_unread_count(request)


@router.patch("/{notification_id}/read", response_model=SuccessResponse[NotificationItem])
async def patch_notification_read(request: Request, notification_id: int) -> SuccessResponse[NotificationItem]:
    return await service.mark_notification_read(request, notification_id)


@router.patch("/read-all", response_model=MessageResponse)
async def patch_notifications_read_all(request: Request) -> MessageResponse:
    return await service.mark_all_notifications_read(request)


@router.post("/test", response_model=MessageResponse)
async def post_test_notification(request: Request) -> MessageResponse:
    return await service.send_test_notification(request)
