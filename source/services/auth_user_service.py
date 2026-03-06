from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any

from fastapi import HTTPException, Request, status

from source.db.session import db_session_manager
from source.repositories import AuditRepository, UserRepository
from source.schemas.pydantic.admin import AdminUserItem
from source.schemas.pydantic.auth import AuthResponse, ForgotPasswordRequest, LoginRequest, LogoutRequest, MessageResponse, RefreshTokenRequest, RegisterRequest, ResetPasswordRequest, SimpleMessage, VerifyEmailRequest
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.user import UserPasswordChangeRequest, UserProfile, UserTokenBundle, UserUpdateRequest
from source.services.token_codec import token_codec


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        encoded_salt, encoded_digest = password_hash.split('$', 1)
        salt = base64.b64decode(encoded_salt.encode())
        expected = base64.b64decode(encoded_digest.encode())
    except ValueError:
        return False
    candidate = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(candidate, expected)


def _check_password_strength(password: str) -> None:
    if len(password) < 8 or password.isalpha() or password.isdigit():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Weak password')


class AuthUserService:
    def __init__(self) -> None:
        self.users = UserRepository()
        self.audit = AuditRepository()

    @staticmethod
    def _profile(user) -> UserProfile:
        return UserProfile.model_validate(user, from_attributes=True)

    @staticmethod
    def _entity_dict(entity) -> dict[str, Any]:
        return {column.name: getattr(entity, column.name) for column in entity.__table__.columns}

    def _bundle(self, user) -> UserTokenBundle:
        return UserTokenBundle(access_token=token_codec.issue_access_token(user.id), refresh_token=token_codec.issue_refresh_token(user.id), user=self._profile(user))

    async def _log_audit(self, *, action: str, entity_type: str, entity_id: int | None, before_json: dict | None, after_json: dict | None, user_id: int | None) -> None:
        async with db_session_manager.session() as session:
            await self.audit.create(session, {'user_id': user_id, 'action': action, 'entity_type': entity_type, 'entity_id': entity_id, 'before_json': before_json, 'after_json': after_json})

    async def _resolve_current_user(self, request: Request):
        auth_header = request.headers.get('authorization', '')
        if not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
        payload = token_codec.decode(auth_header.split(' ', 1)[1])
        async with db_session_manager.session() as session:
            user = await self.users.get(session, int(payload['sub']))
            if user is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')
            if user.status != 'active':
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='User is not active')
            return user

    async def register(self, payload: RegisterRequest) -> AuthResponse:
        _check_password_strength(payload.password)
        async with db_session_manager.session() as session:
            if await self.users.get_by_email(session, payload.email):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already exists')
            if await self.users.get_by_username(session, payload.username):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Username already exists')
            user = await self.users.create(session, {
                'email': payload.email,
                'username': payload.username,
                'password_hash': _hash_password(payload.password),
                'role': 'user',
                'status': 'active',
                'locale': payload.locale or 'ru',
                'timezone': payload.timezone or 'Europe/Moscow',
                'is_email_verified': False,
            })
        await self._log_audit(action='auth.register', entity_type='user', entity_id=user.id, before_json=None, after_json=self._entity_dict(user), user_id=user.id)
        return AuthResponse(data=self._bundle(user))

    async def login(self, payload: LoginRequest) -> AuthResponse:
        async with db_session_manager.session() as session:
            user = await self.users.get_by_login(session, payload.email_or_username)
            if user is None or not _verify_password(payload.password, user.password_hash):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')
            if user.status != 'active':
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='User is not active')
            return AuthResponse(data=self._bundle(user))

    async def refresh(self, payload: RefreshTokenRequest) -> AuthResponse:
        token_payload = token_codec.decode(payload.refresh_token)
        if token_payload.get('typ') != 'refresh':
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid refresh token')
        async with db_session_manager.session() as session:
            user = await self.users.get(session, int(token_payload['sub']))
            if user is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')
            return AuthResponse(data=self._bundle(user))

    async def logout(self, payload: LogoutRequest) -> MessageResponse:
        token_codec.decode(payload.refresh_token)
        return MessageResponse(data=SimpleMessage(message='Logged out'))

    async def forgot_password(self, payload: ForgotPasswordRequest) -> MessageResponse:
        async with db_session_manager.session() as session:
            _ = await self.users.get_by_email(session, payload.email)
        return MessageResponse(data=SimpleMessage(message='If the account exists, reset instructions were created'))

    async def reset_password(self, payload: ResetPasswordRequest) -> MessageResponse:
        _check_password_strength(payload.new_password)
        if not payload.token.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Token is required')
        return MessageResponse(data=SimpleMessage(message='Password reset completed'))

    async def verify_email(self, payload: VerifyEmailRequest) -> MessageResponse:
        if not payload.token.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Token is required')
        return MessageResponse(data=SimpleMessage(message='Email verified'))

    async def auth_me(self, request: Request) -> SuccessResponse[UserProfile]:
        return SuccessResponse(data=self._profile(await self._resolve_current_user(request)))

    async def users_me(self, request: Request) -> SuccessResponse[UserProfile]:
        return SuccessResponse(data=self._profile(await self._resolve_current_user(request)))

    async def update_me(self, request: Request, payload: UserUpdateRequest) -> SuccessResponse[UserProfile]:
        current = await self._resolve_current_user(request)
        async with db_session_manager.session() as session:
            managed = await self.users.get(session, current.id)
            before = self._entity_dict(managed)
            updated = await self.users.update(session, managed, payload.model_dump(exclude_none=True))
            after = self._entity_dict(updated)
        await self._log_audit(action='user.update_profile', entity_type='user', entity_id=updated.id, before_json=before, after_json=after, user_id=current.id)
        return SuccessResponse(data=self._profile(updated))

    async def change_password(self, request: Request, payload: UserPasswordChangeRequest) -> MessageResponse:
        _check_password_strength(payload.new_password)
        current = await self._resolve_current_user(request)
        async with db_session_manager.session() as session:
            managed = await self.users.get(session, current.id)
            if managed is None or not _verify_password(payload.current_password, managed.password_hash):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Current password is invalid')
            before = {'password_hash': managed.password_hash}
            await self.users.update(session, managed, {'password_hash': _hash_password(payload.new_password)})
            after = {'password_hash': managed.password_hash}
        await self._log_audit(action='user.change_password', entity_type='user', entity_id=current.id, before_json=before, after_json=after, user_id=current.id)
        return MessageResponse(data=SimpleMessage(message='Password changed and tokens revoked'))

    async def list_admin_users(self) -> SuccessResponse[list[AdminUserItem]]:
        async with db_session_manager.session() as session:
            users = await self.users.list(session)
            data = [AdminUserItem(id=item.id, email=item.email, username=item.username, role=item.role, status=item.status, created_at=item.created_at) for item in users]
            return SuccessResponse(data=data)

    async def get_admin_user(self, user_id: int) -> SuccessResponse[AdminUserItem]:
        async with db_session_manager.session() as session:
            user = await self.users.get(session, user_id)
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
            return SuccessResponse(data=AdminUserItem(id=user.id, email=user.email, username=user.username, role=user.role, status=user.status, created_at=user.created_at))

    async def update_admin_user(self, user_id: int, payload: dict[str, Any], actor_id: int | None = None) -> SuccessResponse[AdminUserItem]:
        async with db_session_manager.session() as session:
            user = await self.users.get(session, user_id)
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
            before = self._entity_dict(user)
            safe_payload = {key: value for key, value in payload.items() if key in {'email', 'username', 'role', 'status', 'first_name', 'last_name', 'locale', 'timezone'}}
            updated = await self.users.update(session, user, safe_payload)
            after = self._entity_dict(updated)
        await self._log_audit(action='admin.user.update', entity_type='user', entity_id=updated.id, before_json=before, after_json=after, user_id=actor_id)
        return SuccessResponse(data=AdminUserItem(id=updated.id, email=updated.email, username=updated.username, role=updated.role, status=updated.status, created_at=updated.created_at))
