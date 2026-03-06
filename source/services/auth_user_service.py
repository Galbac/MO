from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
import uuid
from typing import Any

from fastapi import HTTPException, Request, status

from source.config.settings import settings
from source.db.session import db_session_manager
from source.repositories import AuditRepository, UserRepository
from source.schemas.pydantic.admin import AdminUserItem
from source.schemas.pydantic.auth import AuthResponse, ForgotPasswordRequest, LoginRequest, LogoutRequest, MessageResponse, RefreshTokenRequest, RegisterRequest, ResetPasswordRequest, SimpleMessage, VerifyEmailRequest
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.user import UserPasswordChangeRequest, UserProfile, UserTokenBundle, UserUpdateRequest
from source.services.runtime_state_store import RuntimeStateStore
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
        self.store = RuntimeStateStore()
        self.security_namespace = 'auth_security'
        self.refresh_namespace = 'refresh_tokens'
        self.action_token_namespace = 'auth_action_tokens'

    @staticmethod
    def _profile(user) -> UserProfile:
        return UserProfile.model_validate(user, from_attributes=True)

    @staticmethod
    def _entity_dict(entity) -> dict[str, Any]:
        return {column.name: getattr(entity, column.name) for column in entity.__table__.columns}

    @staticmethod
    def _json_ready(value: Any) -> Any:
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: AuthUserService._json_ready(item) for key, item in value.items()}
        if isinstance(value, list):
            return [AuthUserService._json_ready(item) for item in value]
        return value

    def _bundle(self, user) -> UserTokenBundle:
        access_token = token_codec.issue_access_token(user.id)
        refresh_token, refresh_payload = token_codec.issue_refresh_token(user.id)
        refresh_store = self.store.read_namespace(self.refresh_namespace, {})
        refresh_store[refresh_payload['jti']] = {'user_id': user.id, 'expires_at': refresh_payload['exp'], 'revoked': False}
        self.store.write_namespace(self.refresh_namespace, refresh_store)
        return UserTokenBundle(access_token=access_token, refresh_token=refresh_token, user=self._profile(user))

    def _issue_action_token(self, *, user_id: int, purpose: str, ttl_minutes: int) -> str:
        now = int(time.time())
        payload = {
            'sub': user_id,
            'typ': purpose,
            'iat': now,
            'exp': now + ttl_minutes * 60,
            'jti': uuid.uuid4().hex,
        }
        store = self.store.read_namespace(self.action_token_namespace, {})
        for token_id, record in list(store.items()):
            if int(record.get('user_id', 0)) == user_id and record.get('purpose') == purpose and not bool(record.get('used')):
                record['used'] = True
                record['revoked_at'] = now
                store[token_id] = record
        store[payload['jti']] = {
            'user_id': user_id,
            'purpose': purpose,
            'expires_at': payload['exp'],
            'issued_at': now,
            'used': False,
        }
        self.store.write_namespace(self.action_token_namespace, store)
        return token_codec.encode(payload)

    def _consume_action_token(self, token: str, *, purpose: str) -> dict[str, Any]:
        payload = token_codec.decode(token)
        if payload.get('typ') != purpose:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
        jti = str(payload.get('jti') or '').strip()
        if not jti:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
        store = self.store.read_namespace(self.action_token_namespace, {})
        record = store.get(jti)
        now = int(time.time())
        if record is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token not found')
        if bool(record.get('used')):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token already used')
        if int(record.get('expires_at', 0)) < now:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token expired')
        if record.get('purpose') != purpose:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
        if int(record.get('user_id', 0)) != int(payload.get('sub', 0)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
        record['used'] = True
        record['used_at'] = now
        store[jti] = record
        self.store.write_namespace(self.action_token_namespace, store)
        return payload

    def _revoke_user_refresh_tokens(self, user_id: int) -> None:
        refresh_store = self.store.read_namespace(self.refresh_namespace, {})
        changed = False
        for token_id, record in refresh_store.items():
            if int(record.get('user_id', 0)) == user_id and not bool(record.get('revoked')):
                record['revoked'] = True
                changed = True
                refresh_store[token_id] = record
        if changed:
            self.store.write_namespace(self.refresh_namespace, refresh_store)

    async def _log_audit(self, *, action: str, entity_type: str, entity_id: int | None, before_json: dict | None, after_json: dict | None, user_id: int | None) -> None:
        async with db_session_manager.session() as session:
            await self.audit.create(session, {'user_id': user_id, 'action': action, 'entity_type': entity_type, 'entity_id': entity_id, 'before_json': before_json, 'after_json': after_json})

    def _client_ip(self, request: Request | None) -> str:
        if request is None or request.client is None or not request.client.host:
            return 'unknown'
        return request.client.host

    def _login_key(self, request: Request | None, login_value: str) -> str:
        return f"{self._client_ip(request)}::{login_value.strip().lower()}"

    def _rate_limit_guard(self, request: Request | None, login_value: str) -> None:
        state = self.store.read_namespace(self.security_namespace, {'login_attempts': {}})
        key = self._login_key(request, login_value)
        now = int(time.time())
        window = settings.auth.login_rate_limit_window_seconds
        lockout = settings.auth.brute_force_lockout_seconds
        record = state['login_attempts'].get(key, {'failures': [], 'locked_until': 0})
        failures = [item for item in record.get('failures', []) if now - int(item) <= window]
        locked_until = int(record.get('locked_until', 0))
        if locked_until > now:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Too many login attempts')
        if len(failures) >= settings.auth.login_rate_limit_max_attempts:
            record = {'failures': failures, 'locked_until': now + lockout}
            state['login_attempts'][key] = record
            self.store.write_namespace(self.security_namespace, state)
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Too many login attempts')

    def _register_login_failure(self, request: Request | None, login_value: str) -> None:
        state = self.store.read_namespace(self.security_namespace, {'login_attempts': {}})
        key = self._login_key(request, login_value)
        now = int(time.time())
        window = settings.auth.login_rate_limit_window_seconds
        record = state['login_attempts'].get(key, {'failures': [], 'locked_until': 0})
        failures = [item for item in record.get('failures', []) if now - int(item) <= window]
        failures.append(now)
        locked_until = record.get('locked_until', 0)
        if len(failures) >= settings.auth.login_rate_limit_max_attempts:
            locked_until = now + settings.auth.brute_force_lockout_seconds
        state['login_attempts'][key] = {'failures': failures, 'locked_until': locked_until}
        self.store.write_namespace(self.security_namespace, state)

    def _clear_login_failures(self, request: Request | None, login_value: str) -> None:
        state = self.store.read_namespace(self.security_namespace, {'login_attempts': {}})
        key = self._login_key(request, login_value)
        state['login_attempts'].pop(key, None)
        self.store.write_namespace(self.security_namespace, state)

    def _consume_refresh_token(self, refresh_token: str, *, revoke_only: bool) -> dict[str, Any]:
        payload = token_codec.decode(refresh_token)
        if payload.get('typ') != 'refresh':
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid refresh token')
        jti = payload.get('jti')
        if not jti:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid refresh token')
        refresh_store = self.store.read_namespace(self.refresh_namespace, {})
        record = refresh_store.get(jti)
        now = int(time.time())
        if record is None or bool(record.get('revoked')) or int(record.get('expires_at', 0)) < now:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Refresh token revoked')
        if settings.auth.refresh_token_rotation_enabled or revoke_only:
            record['revoked'] = True
            refresh_store[jti] = record
            self.store.write_namespace(self.refresh_namespace, refresh_store)
        return payload

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

    async def register(self, request: Request | None, payload: RegisterRequest) -> AuthResponse:
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
        self._issue_action_token(
            user_id=user.id,
            purpose='verify_email',
            ttl_minutes=settings.auth.email_verification_token_ttl_minutes,
        )
        return AuthResponse(data=self._bundle(user))

    async def login(self, request: Request | None, payload: LoginRequest) -> AuthResponse:
        self._rate_limit_guard(request, payload.email_or_username)
        async with db_session_manager.session() as session:
            user = await self.users.get_by_login(session, payload.email_or_username)
            if user is None or not _verify_password(payload.password, user.password_hash):
                self._register_login_failure(request, payload.email_or_username)
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')
            if user.status != 'active':
                self._register_login_failure(request, payload.email_or_username)
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='User is not active')
        self._clear_login_failures(request, payload.email_or_username)
        return AuthResponse(data=self._bundle(user))

    async def refresh(self, request: Request | None, payload: RefreshTokenRequest) -> AuthResponse:
        token_payload = self._consume_refresh_token(payload.refresh_token, revoke_only=False)
        async with db_session_manager.session() as session:
            user = await self.users.get(session, int(token_payload['sub']))
            if user is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')
            if user.status != 'active':
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='User is not active')
            return AuthResponse(data=self._bundle(user))

    async def logout(self, request: Request | None, payload: LogoutRequest) -> MessageResponse:
        self._consume_refresh_token(payload.refresh_token, revoke_only=True)
        return MessageResponse(data=SimpleMessage(message='Logged out'))

    async def forgot_password(self, request: Request | None, payload: ForgotPasswordRequest) -> MessageResponse:
        async with db_session_manager.session() as session:
            user = await self.users.get_by_email(session, payload.email)
        if user is not None and user.status == 'active':
            self._issue_action_token(
                user_id=user.id,
                purpose='password_reset',
                ttl_minutes=settings.auth.password_reset_token_ttl_minutes,
            )
        return MessageResponse(data=SimpleMessage(message='If the account exists, reset instructions were created'))

    async def reset_password(self, payload: ResetPasswordRequest) -> MessageResponse:
        _check_password_strength(payload.new_password)
        if not payload.token.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Token is required')
        token_payload = self._consume_action_token(payload.token, purpose='password_reset')
        user_id = int(token_payload['sub'])
        async with db_session_manager.session() as session:
            user = await self.users.get(session, user_id)
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
            before = {'password_hash': user.password_hash}
            updated = await self.users.update(session, user, {'password_hash': _hash_password(payload.new_password)})
            after = {'password_hash': updated.password_hash}
        self._revoke_user_refresh_tokens(user_id)
        await self._log_audit(action='auth.reset_password', entity_type='user', entity_id=user_id, before_json=before, after_json=after, user_id=user_id)
        return MessageResponse(data=SimpleMessage(message='Password reset completed'))

    async def verify_email(self, payload: VerifyEmailRequest) -> MessageResponse:
        if not payload.token.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Token is required')
        token_payload = self._consume_action_token(payload.token, purpose='verify_email')
        user_id = int(token_payload['sub'])
        async with db_session_manager.session() as session:
            user = await self.users.get(session, user_id)
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
            before = {'is_email_verified': user.is_email_verified}
            updated = await self.users.update(session, user, {'is_email_verified': True})
            after = {'is_email_verified': updated.is_email_verified}
        await self._log_audit(action='auth.verify_email', entity_type='user', entity_id=user_id, before_json=before, after_json=after, user_id=user_id)
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

    async def list_admin_users(self, *, search: str | None = None, role: str | None = None, status: str | None = None) -> SuccessResponse[list[AdminUserItem]]:
        async with db_session_manager.session() as session:
            users = await self.users.list(session, search=search, role=role, status=status)
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
            safe_payload = {key: value for key, value in payload.items() if key in {'email', 'username', 'role', 'status', 'first_name', 'last_name', 'locale', 'timezone', 'quiet_hours_start', 'quiet_hours_end'}}
            updated = await self.users.update(session, user, safe_payload)
            after = self._entity_dict(updated)
        await self._log_audit(action='admin.user.update', entity_type='user', entity_id=updated.id, before_json=before, after_json=after, user_id=actor_id)
        return SuccessResponse(data=AdminUserItem(id=updated.id, email=updated.email, username=updated.username, role=updated.role, status=updated.status, created_at=updated.created_at))


    def _revoke_user_refresh_tokens(self, user_id: int) -> None:
        refresh_store = self.store.read_namespace(self.refresh_namespace, {})
        changed = False
        for key, value in refresh_store.items():
            if int(value.get('user_id', 0)) == user_id and not bool(value.get('revoked')):
                value['revoked'] = True
                refresh_store[key] = value
                changed = True
        if changed:
            self.store.write_namespace(self.refresh_namespace, refresh_store)

    async def delete_admin_user(self, user_id: int, actor_id: int | None = None) -> MessageResponse:
        async with db_session_manager.session() as session:
            user = await self.users.get(session, user_id)
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
            before = self._entity_dict(user)
            tombstone = f'deleted-{user.id}'
            updated = await self.users.update(session, user, {
                'status': 'deleted',
                'email': f'{tombstone}@example.com',
                'username': tombstone,
            })
            after = self._entity_dict(updated)
        self._revoke_user_refresh_tokens(user_id)
        await self._log_audit(action='admin.user.delete', entity_type='user', entity_id=user_id, before_json=before, after_json=after, user_id=actor_id)
        return MessageResponse(data=SimpleMessage(message='User soft deleted'))
