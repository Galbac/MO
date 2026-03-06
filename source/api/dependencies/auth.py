from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status

from source.services import AuthUserService

auth_service = AuthUserService()


async def require_authenticated_user(request: Request):
    user = await auth_service._resolve_current_user(request)
    request.state.current_user = user
    return user


def require_roles(*roles: str) -> Callable:
    async def dependency(request: Request, user = Depends(require_authenticated_user)):
        allowed = set(roles)
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Insufficient permissions')
        request.state.current_user = user
        return user

    return dependency
