from fastapi import APIRouter, Request

from source.schemas.pydantic.admin import AdminActionResult, AdminUserItem
from source.schemas.pydantic.common import SuccessResponse
from source.services import AuthUserService

router = APIRouter(prefix="/users", tags=["admin-users"])
service = AuthUserService()


@router.get("", response_model=SuccessResponse[list[AdminUserItem]])
async def list_admin_users(search: str | None = None, role: str | None = None, status: str | None = None) -> SuccessResponse[list[AdminUserItem]]:
    return await service.list_admin_users(search=search, role=role, status=status)


@router.get("/{user_id}", response_model=SuccessResponse[AdminUserItem])
async def get_admin_user(user_id: int) -> SuccessResponse[AdminUserItem]:
    return await service.get_admin_user(user_id)


@router.patch("/{user_id}", response_model=SuccessResponse[AdminUserItem])
async def patch_admin_user(request: Request, user_id: int, payload: dict) -> SuccessResponse[AdminUserItem]:
    return await service.update_admin_user(user_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.patch("/{user_id}/status", response_model=SuccessResponse[AdminUserItem])
async def patch_admin_user_status(request: Request, user_id: int, payload: dict) -> SuccessResponse[AdminUserItem]:
    return await service.update_admin_user(user_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.patch("/{user_id}/role", response_model=SuccessResponse[AdminUserItem])
async def patch_admin_user_role(request: Request, user_id: int, payload: dict) -> SuccessResponse[AdminUserItem]:
    return await service.update_admin_user(user_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.delete("/{user_id}", response_model=SuccessResponse[AdminActionResult])
async def delete_admin_user(request: Request, user_id: int) -> SuccessResponse[AdminActionResult]:
    return await service.delete_admin_user(user_id, actor_id=getattr(request.state.current_user, 'id', None))
