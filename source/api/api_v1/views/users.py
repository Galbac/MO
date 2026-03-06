from fastapi import APIRouter, Depends, Request

from source.api.dependencies.auth import require_authenticated_user
from source.schemas.pydantic.common import ActionResult, SuccessResponse
from source.schemas.pydantic.notification import NotificationItem
from source.schemas.pydantic.user import (
    FavoriteCreateRequest,
    FavoriteItem,
    NotificationSubscriptionCreateRequest,
    NotificationSubscriptionItem,
    NotificationSubscriptionUpdateRequest,
    UserPasswordChangeRequest,
    UserProfile,
    UserUpdateRequest,
)
from source.services import AuthUserService, UserEngagementService

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_authenticated_user)])
service = AuthUserService()
engagement = UserEngagementService()


@router.get("/me", response_model=SuccessResponse[UserProfile])
async def get_me(request: Request) -> SuccessResponse[UserProfile]:
    return await service.users_me(request)


@router.patch("/me", response_model=SuccessResponse[UserProfile])
async def patch_me(request: Request, payload: UserUpdateRequest) -> SuccessResponse[UserProfile]:
    return await service.update_me(request, payload)


@router.patch("/me/password", response_model=SuccessResponse[ActionResult])
async def patch_me_password(request: Request, payload: UserPasswordChangeRequest) -> SuccessResponse[ActionResult]:
    return await service.change_password(request, payload)


@router.get("/me/favorites", response_model=SuccessResponse[list[FavoriteItem]])
async def get_favorites(request: Request) -> SuccessResponse[list[FavoriteItem]]:
    return await engagement.list_favorites(request)


@router.post("/me/favorites", response_model=SuccessResponse[FavoriteItem])
async def create_favorite(request: Request, payload: FavoriteCreateRequest) -> SuccessResponse[FavoriteItem]:
    return await engagement.create_favorite(request, payload)


@router.delete("/me/favorites/{favorite_id}", response_model=SuccessResponse[ActionResult])
async def delete_favorite(request: Request, favorite_id: int) -> SuccessResponse[ActionResult]:
    return await engagement.delete_favorite(request, favorite_id)


@router.get("/me/subscriptions", response_model=SuccessResponse[list[NotificationSubscriptionItem]])
async def get_subscriptions(request: Request) -> SuccessResponse[list[NotificationSubscriptionItem]]:
    return await engagement.list_subscriptions(request)


@router.post("/me/subscriptions", response_model=SuccessResponse[NotificationSubscriptionItem])
async def create_subscription(request: Request, payload: NotificationSubscriptionCreateRequest) -> SuccessResponse[NotificationSubscriptionItem]:
    return await engagement.create_subscription(request, payload)


@router.patch("/me/subscriptions/{subscription_id}", response_model=SuccessResponse[NotificationSubscriptionItem])
async def patch_subscription(request: Request, subscription_id: int, payload: NotificationSubscriptionUpdateRequest) -> SuccessResponse[NotificationSubscriptionItem]:
    return await engagement.update_subscription(request, subscription_id, payload)


@router.delete("/me/subscriptions/{subscription_id}", response_model=SuccessResponse[ActionResult])
async def delete_subscription(request: Request, subscription_id: int) -> SuccessResponse[ActionResult]:
    return await engagement.delete_subscription(request, subscription_id)


@router.get("/me/notifications", response_model=SuccessResponse[list[NotificationItem]])
async def get_me_notifications(request: Request) -> SuccessResponse[list[NotificationItem]]:
    return await engagement.list_notifications(request)


@router.patch("/me/notifications/{notification_id}/read", response_model=SuccessResponse[NotificationItem])
async def patch_me_notification_read(request: Request, notification_id: int) -> SuccessResponse[NotificationItem]:
    return await engagement.mark_notification_read(request, notification_id)


@router.patch("/me/notifications/read-all", response_model=SuccessResponse[ActionResult])
async def patch_me_notifications_read_all(request: Request) -> SuccessResponse[ActionResult]:
    return await engagement.mark_all_notifications_read(request)
