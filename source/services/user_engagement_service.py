from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from source.config.settings import settings
from source.db.session import db_session_manager
from source.repositories import EngagementRepository, MatchRepository, NewsRepository, PlayerRepository, TournamentRepository
from source.schemas.pydantic.common import ActionResult, SuccessResponse
from source.schemas.pydantic.notification import NotificationItem, NotificationUnreadCount
from source.schemas.pydantic.user import (
    FavoriteCreateRequest,
    FavoriteItem,
    MatchReminderCreateRequest,
    MatchReminderItem,
    MatchReminderUpdateRequest,
    NotificationSubscriptionCreateRequest,
    NotificationSubscriptionItem,
    NotificationSubscriptionUpdateRequest,
    PushSubscriptionCreateRequest,
    PushSubscriptionItem,
    PushSubscriptionTestRequest,
    SmartFeedBundle,
    UserCalendarOverview,
)
from source.services.auth_user_service import AuthUserService
from source.services.workflow_service import WorkflowService


class UserEngagementService:
    def __init__(self) -> None:
        self.repo = EngagementRepository()
        self.auth = AuthUserService()
        self.players = PlayerRepository()
        self.tournaments = TournamentRepository()
        self.matches = MatchRepository()
        self.news = NewsRepository()
        self.workflows = WorkflowService()

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
    def _reminder_at(scheduled_at: datetime, remind_before_minutes: int) -> datetime:
        return scheduled_at - timedelta(minutes=int(remind_before_minutes))

    async def _build_reminder_item(self, session: AsyncSession, reminder, *, source: str = 'manual') -> MatchReminderItem | None:
        match = await self.matches.get(session, reminder.match_id)
        if match is None:
            return None
        tournament = await self.tournaments.get(session, match.tournament_id)
        player1 = await self.players.get(session, match.player1_id)
        player2 = await self.players.get(session, match.player2_id)
        title = f'{player1.full_name if player1 else "Игрок 1"} против {player2.full_name if player2 else "Игрок 2"}'
        return MatchReminderItem(
            id=reminder.id,
            user_id=reminder.user_id,
            match_id=match.id,
            match_slug=match.slug,
            title=title,
            tournament_name=tournament.name if tournament else match.slug,
            scheduled_at=match.scheduled_at,
            remind_before_minutes=reminder.remind_before_minutes,
            channel=reminder.channel,
            is_active=reminder.is_active,
            reminder_at=self._reminder_at(match.scheduled_at, reminder.remind_before_minutes),
            source=source,
        )

    @staticmethod
    def _upcoming_match(match) -> bool:
        return match.status in {'scheduled', 'about_to_start', 'live', 'suspended', 'interrupted'} and match.scheduled_at is not None

    async def _tracked_matches(self, session: AsyncSession, user_id: int) -> list:
        favorites = await self.repo.list_favorites(session, user_id)
        subscriptions = await self.repo.list_subscriptions(session, user_id)
        tracked_matches: dict[int, object] = {}

        async def push_match(item) -> None:
            if item and self._upcoming_match(item):
                tracked_matches[item.id] = item

        for item in favorites + subscriptions:
            if item.entity_type == 'match':
                await push_match(await self.matches.get(session, item.entity_id))
                continue
            if item.entity_type == 'player':
                for match in await self.players.get_matches(session, item.entity_id):
                    await push_match(match)
                continue
            if item.entity_type == 'tournament':
                for match in await self.tournaments.get_matches(session, item.entity_id):
                    await push_match(match)

        return sorted(tracked_matches.values(), key=lambda item: item.scheduled_at)

    async def list_calendar(self, request: Request) -> SuccessResponse[UserCalendarOverview]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            reminders = await self.repo.list_match_reminders(session, user_id)
            reminder_map = {item.match_id: item for item in reminders}
            items: list[MatchReminderItem] = []
            for reminder in reminders:
                built = await self._build_reminder_item(session, reminder, source='manual')
                if built is not None:
                    items.append(built)
            for match in await self._tracked_matches(session, user_id):
                if match.id in reminder_map:
                    continue
                synthetic = type('SyntheticReminder', (), {
                    'id': 0,
                    'user_id': user_id,
                    'match_id': match.id,
                    'remind_before_minutes': 30,
                    'channel': 'web',
                    'is_active': True,
                })()
                built = await self._build_reminder_item(session, synthetic, source='tracked')
                if built is not None:
                    items.append(built)
        items.sort(key=lambda item: item.scheduled_at)
        return SuccessResponse(
            data=UserCalendarOverview(
                items=items,
                total=len(items),
                active=sum(1 for item in items if item.is_active),
                next_item_at=items[0].scheduled_at if items else None,
            )
        )

    async def create_match_reminder(self, request: Request, payload: MatchReminderCreateRequest) -> SuccessResponse[MatchReminderItem]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, payload.match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            existing = await self.repo.find_match_reminder(session, user_id, payload.match_id)
            if existing is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Reminder already exists')
            reminder = await self.repo.create_match_reminder(
                session,
                {
                    'user_id': user_id,
                    'match_id': payload.match_id,
                    'remind_before_minutes': payload.remind_before_minutes,
                    'channel': payload.channel,
                    'is_active': True,
                },
            )
            built = await self._build_reminder_item(session, reminder)
            return SuccessResponse(data=built)

    async def update_match_reminder(self, request: Request, reminder_id: int, payload: MatchReminderUpdateRequest) -> SuccessResponse[MatchReminderItem]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            reminder = await self.repo.get_match_reminder(session, reminder_id, user_id)
            if reminder is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Reminder not found')
            updated = await self.repo.update_match_reminder(session, reminder, payload.model_dump(exclude_none=True))
            built = await self._build_reminder_item(session, updated)
            return SuccessResponse(data=built)

    async def delete_match_reminder(self, request: Request, reminder_id: int) -> SuccessResponse[ActionResult]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            reminder = await self.repo.get_match_reminder(session, reminder_id, user_id)
            if reminder is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Reminder not found')
            await self.repo.delete_match_reminder(session, reminder)
        return self._action_result(action='reminder.delete', resource_type='reminder', resource_id=reminder_id, message='Напоминание удалено')

    async def get_smart_feed(self, request: Request) -> SuccessResponse[SmartFeedBundle]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            favorites = await self.repo.list_favorites(session, user_id)
            subscriptions = await self.repo.list_subscriptions(session, user_id)
            player_ids = list(dict.fromkeys([item.entity_id for item in favorites + subscriptions if item.entity_type == 'player']))[:6]
            tournament_ids = list(dict.fromkeys([item.entity_id for item in favorites + subscriptions if item.entity_type == 'tournament']))[:6]
            tracked_matches = (await self._tracked_matches(session, user_id))[:6]
            players = []
            for player_id in player_ids:
                player = await self.players.get(session, player_id)
                if player is not None:
                    players.append({
                        'id': player.id,
                        'slug': player.slug,
                        'full_name': player.full_name,
                        'country_code': player.country_code,
                        'current_rank': player.current_rank,
                        'current_points': player.current_points,
                        'photo_url': player.photo_url,
                    })
            tournaments = []
            for tournament_id in tournament_ids:
                tournament = await self.tournaments.get(session, tournament_id)
                if tournament is not None:
                    tournaments.append({
                        'id': tournament.id,
                        'slug': tournament.slug,
                        'name': tournament.name,
                        'category': tournament.category,
                        'surface': tournament.surface,
                        'season_year': tournament.season_year,
                        'status': tournament.status,
                        'city': tournament.city,
                        'country_code': tournament.country_code,
                        'start_date': tournament.start_date.isoformat() if tournament.start_date else None,
                        'end_date': tournament.end_date.isoformat() if tournament.end_date else None,
                    })
            matches = []
            for match in tracked_matches:
                tournament = await self.tournaments.get(session, match.tournament_id)
                player1 = await self.players.get(session, match.player1_id)
                player2 = await self.players.get(session, match.player2_id)
                matches.append({
                    'id': match.id,
                    'slug': match.slug,
                    'status': match.status,
                    'scheduled_at': match.scheduled_at.isoformat(),
                    'player1_name': player1.full_name if player1 else 'Игрок 1',
                    'player2_name': player2.full_name if player2 else 'Игрок 2',
                    'player1_id': match.player1_id,
                    'player2_id': match.player2_id,
                    'tournament_id': match.tournament_id,
                    'tournament_name': tournament.name if tournament else match.slug,
                    'round_code': match.round_code,
                    'score_summary': match.score_summary,
                })
        highlights = []
        if players:
            highlights.append(f'В фокусе игроков: {len(players)}')
        if tournaments:
            highlights.append(f'Отслеживаемых турниров: {len(tournaments)}')
        if matches:
            highlights.append(f'Ближайших матчей в ленте: {len(matches)}')
        return SuccessResponse(data=SmartFeedBundle(players=players, tournaments=tournaments, matches=matches, highlights=highlights))

    async def list_push_subscriptions(self, request: Request) -> SuccessResponse[list[PushSubscriptionItem]]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            items = await self.repo.list_push_subscriptions(session, user_id)
            return SuccessResponse(
                data=[
                    PushSubscriptionItem(
                        id=item.id,
                        user_id=item.user_id,
                        endpoint=item.endpoint,
                        device_label=item.device_label,
                        permission=item.permission,
                        is_active=item.is_active,
                        created_at=item.created_at,
                    )
                    for item in items
                ]
            )

    async def create_push_subscription(self, request: Request, payload: PushSubscriptionCreateRequest) -> SuccessResponse[PushSubscriptionItem]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            existing = await self.repo.find_push_subscription(session, user_id, payload.endpoint)
            data = payload.model_dump()
            data['user_id'] = user_id
            data['is_active'] = payload.permission == 'granted'
            if existing is None:
                item = await self.repo.create_push_subscription(session, data)
            else:
                item = await self.repo.update_push_subscription(session, existing, data)
            return SuccessResponse(
                data=PushSubscriptionItem(
                    id=item.id,
                    user_id=item.user_id,
                    endpoint=item.endpoint,
                    device_label=item.device_label,
                    permission=item.permission,
                    is_active=item.is_active,
                    created_at=item.created_at,
                )
            )

    async def delete_push_subscription(self, request: Request, subscription_id: int) -> SuccessResponse[ActionResult]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            item = await self.repo.get_push_subscription(session, subscription_id, user_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Push subscription not found')
            await self.repo.delete_push_subscription(session, item)
        return self._action_result(action='push_subscription.delete', resource_type='push_subscription', resource_id=subscription_id, message='Браузерное устройство удалено')

    async def test_push_subscription(self, request: Request, payload: PushSubscriptionTestRequest) -> SuccessResponse[ActionResult]:
        user_id = await self._current_user_id(request)
        async with db_session_manager.session() as session:
            subscriptions = await self.repo.list_push_subscriptions(session, user_id)
            active = [item for item in subscriptions if item.is_active and item.permission == 'granted']
            item = await self.repo.create_notification(
                session,
                {
                    'user_id': user_id,
                    'type': 'test',
                    'title': payload.title,
                    'body': payload.body,
                    'payload_json': {'source': 'browser_push'},
                    'status': 'unread',
                    'read_at': None,
                },
            )
            for subscription in active:
                self.workflows._record_delivery(
                    user_id=user_id,
                    channel='push',
                    notification_type='test',
                    title=payload.title,
                    entity_type='notification',
                    entity_id=item.id,
                    status='queued',
                    reason=f'browser:{subscription.device_label or "device"}',
                )
        return self._action_result(
            action='push_subscription.test',
            resource_type='notification',
            resource_id=item.id,
            message='Тестовое браузерное уведомление поставлено в очередь',
            details={'active_devices': len(active)},
        )

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
            for channel in settings.notifications.active_channels:
                self.workflows._record_delivery(user_id=user_id, channel=channel, notification_type='test', title='Test notification', entity_type='notification', entity_id=item.id, status='sent' if channel == 'web' else 'queued', reason=None if channel == 'web' else 'transport_not_configured')
            inactive_channels = [item for item in settings.notifications.allowed_channels if item not in settings.notifications.active_channels]
            return SuccessResponse(
                data=ActionResult(
                    action='notification.test',
                    status='ok',
                    message='Test notification sent',
                    resource_type='notification',
                    resource_id=item.id,
                    details={'type': 'test', 'active_channels': list(settings.notifications.active_channels), 'inactive_channels': inactive_channels, 'delivery_backend': 'web+runtime-log'},
                ),
                meta={'user_id': user_id, 'delivery_channels': list(settings.notifications.active_channels), 'inactive_channels': inactive_channels},
            )
