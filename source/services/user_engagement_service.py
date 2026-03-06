from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from source.config.settings import settings
from source.db.session import db_session_manager
from source.repositories import EngagementRepository, MatchRepository, NewsRepository, PlayerRepository, TournamentRepository
from source.schemas.pydantic.common import ActionResult, SuccessResponse
from source.schemas.pydantic.notification import NotificationItem, NotificationUnreadCount
from source.schemas.pydantic.user import FavoriteCreateRequest, FavoriteItem, NotificationSubscriptionCreateRequest, NotificationSubscriptionItem, NotificationSubscriptionUpdateRequest
from source.services.auth_user_service import AuthUserService


class UserEngagementService:
    def __init__(self) -> None:
        self.repo = EngagementRepository()
        self.auth = AuthUserService()
        self.players = PlayerRepository()
        self.tournaments = TournamentRepository()
        self.matches = MatchRepository()
        self.news = NewsRepository()

    async def _current_user_id(self, request: Request) -> int:
        user = await self.auth._resolve_current_user(request)
        return user.id

    async def _resolve_entity_name(self, session: AsyncSession, entity_type: str, entity_id: int) -> str | None:
        if entity_type == 'player':
            entity = await self.players.get(session, entity_id)
            return entity.full_name if entity else None
        if entity_type == 'tournament':
            entity = await self.tournaments.get(session, entity_id)
            return entity.name if entity else None
        if entity_type == 'match':
            entity = await self.matches.get(session, entity_id)
            if entity is None:
                return None
            player1 = await self.players.get(session, entity.player1_id)
            player2 = await self.players.get(session, entity.player2_id)
            if player1 and player2:
                return f'{player1.full_name} vs {player2.full_name}'
            return entity.slug
        if entity_type == 'news':
            entity = await self.news.get(session, entity_id)
            return entity.title if entity else None
        return None

    async def _require_entity_name(self, session: AsyncSession, entity_type: str, entity_id: int) -> str:
        entity_name = await self._resolve_entity_name(session, entity_type, entity_id)
        if entity_name is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Entity not found')
        return entity_name

    @staticmethod
    def _normalize_unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for value in values:
            item = str(value).strip()
            if not item or item in seen:
                continue
            seen.add(item)
            normalized.append(item)
        return normalized

    def _validate_subscription_payload(self, notification_types: list[str], channels: list[str]) -> tuple[list[str], list[str]]:
        normalized_types = self._normalize_unique(notification_types)
        normalized_channels = self._normalize_unique(channels)
        if not normalized_types:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='notification_types is required')
        if not normalized_channels:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='channels is required')
        if any(item not in settings.notifications.allowed_types for item in normalized_types):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Unsupported notification type')
        if any(item not in settings.notifications.allowed_channels for item in normalized_channels):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Unsupported notification channel')
        return normalized_types, normalized_channels

    @staticmethod
    def _notification_item(item) -> NotificationItem:
        return NotificationItem(id=item.id, type=item.type, title=item.title, body=item.body, payload_json=item.payload_json or {}, status=item.status, read_at=item.read_at, created_at=item.created_at)

    @staticmethod
    def _action_result(
        *,
        action: str,
        resource_type: str | None = None,
        resource_id: int | None = None,
        message: str | None = None,
        status: str = 'ok',
        details: dict | None = None,
    ) -> SuccessResponse[ActionResult]:
        return SuccessResponse(
            data=ActionResult(
                action=action,
                status=status,
                message=message,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
            )
        )

    async def list_favorites(self, request: Request) -> SuccessResponse[list[FavoriteItem]]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            items = await self.repo.list_favorites(session, user_id)
            data = []
            for item in items:
                entity_name = await self._resolve_entity_name(session, item.entity_type, item.entity_id)
                data.append(FavoriteItem(id=item.id, user_id=item.user_id, entity_type=item.entity_type, entity_id=item.entity_id, entity_name=entity_name or f'{item.entity_type}:{item.entity_id}'))
            return SuccessResponse(data=data)

    async def create_favorite(self, request: Request, payload: FavoriteCreateRequest) -> SuccessResponse[FavoriteItem]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            entity_name = await self._require_entity_name(session, payload.entity_type, payload.entity_id)
            exists = await self.repo.find_favorite(session, user_id, payload.entity_type, payload.entity_id)
            if exists is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Favorite already exists')
            item = await self.repo.create_favorite(session, {'user_id': user_id, 'entity_type': payload.entity_type, 'entity_id': payload.entity_id})
            return SuccessResponse(data=FavoriteItem(id=item.id, user_id=item.user_id, entity_type=item.entity_type, entity_id=item.entity_id, entity_name=entity_name))

    async def delete_favorite(self, request: Request, favorite_id: int) -> SuccessResponse[ActionResult]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            favorite = await self.repo.get_favorite(session, favorite_id, user_id)
            if favorite is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Favorite not found')
            details = {'entity_type': favorite.entity_type, 'entity_id': favorite.entity_id}
            await self.repo.delete_favorite(session, favorite)
            return self._action_result(action='favorite.delete', resource_type='favorite', resource_id=favorite_id, message='Favorite deleted', details=details)

    async def list_subscriptions(self, request: Request) -> SuccessResponse[list[NotificationSubscriptionItem]]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            items = await self.repo.list_subscriptions(session, user_id)
            return SuccessResponse(data=[NotificationSubscriptionItem(id=item.id, user_id=item.user_id, entity_type=item.entity_type, entity_id=item.entity_id, notification_types=list(item.notification_types or []), channels=list(item.channels or []), is_active=item.is_active) for item in items])

    async def create_subscription(self, request: Request, payload: NotificationSubscriptionCreateRequest) -> SuccessResponse[NotificationSubscriptionItem]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            await self._require_entity_name(session, payload.entity_type, payload.entity_id)
            notification_types, channels = self._validate_subscription_payload(payload.notification_types, payload.channels)
            exists = await self.repo.find_subscription(session, user_id, payload.entity_type, payload.entity_id)
            if exists is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Subscription already exists')
            item = await self.repo.create_subscription(session, {'user_id': user_id, 'entity_type': payload.entity_type, 'entity_id': payload.entity_id, 'notification_types': notification_types, 'channels': channels, 'is_active': True})
            return SuccessResponse(data=NotificationSubscriptionItem(id=item.id, user_id=item.user_id, entity_type=item.entity_type, entity_id=item.entity_id, notification_types=list(item.notification_types or []), channels=list(item.channels or []), is_active=item.is_active))

    async def update_subscription(self, request: Request, subscription_id: int, payload: NotificationSubscriptionUpdateRequest) -> SuccessResponse[NotificationSubscriptionItem]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            item = await self.repo.get_subscription(session, subscription_id, user_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subscription not found')
            update_payload = payload.model_dump(exclude_none=True)
            if 'notification_types' in update_payload or 'channels' in update_payload:
                notification_types = update_payload.get('notification_types', list(item.notification_types or []))
                channels = update_payload.get('channels', list(item.channels or []))
                normalized_types, normalized_channels = self._validate_subscription_payload(notification_types, channels)
                update_payload['notification_types'] = normalized_types
                update_payload['channels'] = normalized_channels
            updated = await self.repo.update_subscription(session, item, update_payload)
            return SuccessResponse(data=NotificationSubscriptionItem(id=updated.id, user_id=updated.user_id, entity_type=updated.entity_type, entity_id=updated.entity_id, notification_types=list(updated.notification_types or []), channels=list(updated.channels or []), is_active=updated.is_active))

    async def delete_subscription(self, request: Request, subscription_id: int) -> SuccessResponse[ActionResult]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            item = await self.repo.get_subscription(session, subscription_id, user_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subscription not found')
            details = {
                'entity_type': item.entity_type,
                'entity_id': item.entity_id,
                'notification_types': list(item.notification_types or []),
                'channels': list(item.channels or []),
            }
            await self.repo.delete_subscription(session, item)
            return self._action_result(action='subscription.delete', resource_type='subscription', resource_id=subscription_id, message='Subscription deleted', details=details)

    async def list_notifications(self, request: Request) -> SuccessResponse[list[NotificationItem]]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            items = await self.repo.list_notifications(session, user_id)
            return SuccessResponse(data=[self._notification_item(item) for item in items])

    async def get_unread_count(self, request: Request) -> SuccessResponse[NotificationUnreadCount]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            total = await self.repo.count_unread_notifications(session, user_id)
            return SuccessResponse(data=NotificationUnreadCount(unread_count=total))

    async def mark_notification_read(self, request: Request, notification_id: int) -> SuccessResponse[NotificationItem]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            item = await self.repo.get_notification(session, notification_id, user_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Notification not found')
            updated = await self.repo.mark_notification_read(session, item, datetime.now(tz=UTC))
            return SuccessResponse(data=self._notification_item(updated))

    async def mark_all_notifications_read(self, request: Request) -> SuccessResponse[ActionResult]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            unread_before = await self.repo.count_unread_notifications(session, user_id)
            await self.repo.mark_all_notifications_read(session, user_id, datetime.now(tz=UTC))
            return self._action_result(action='notification.read_all', resource_type='notification', message='All notifications marked as read', details={'updated_count': unread_before})

    async def send_test_notification(self, request: Request) -> SuccessResponse[ActionResult]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            item = await self.repo.create_notification(session, {'user_id': user_id, 'type': 'test', 'title': 'Test notification', 'body': 'This is a test notification.', 'payload_json': {'source': 'api'}, 'status': 'unread', 'read_at': None})
            return self._action_result(action='notification.test', resource_type='notification', resource_id=item.id, message='Test notification sent', details={'type': 'test'})
