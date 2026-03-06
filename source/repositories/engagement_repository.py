from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import FavoriteEntity, Notification, NotificationSubscription


class EngagementRepository:
    async def list_favorites(self, session: AsyncSession, user_id: int) -> list[FavoriteEntity]:
        stmt = select(FavoriteEntity).where(FavoriteEntity.user_id == user_id).order_by(FavoriteEntity.id.asc())
        return list((await session.scalars(stmt)).all())

    async def get_favorite(self, session: AsyncSession, favorite_id: int, user_id: int) -> FavoriteEntity | None:
        stmt = select(FavoriteEntity).where(FavoriteEntity.id == favorite_id, FavoriteEntity.user_id == user_id)
        return await session.scalar(stmt)

    async def find_favorite(self, session: AsyncSession, user_id: int, entity_type: str, entity_id: int) -> FavoriteEntity | None:
        stmt = select(FavoriteEntity).where(FavoriteEntity.user_id == user_id, FavoriteEntity.entity_type == entity_type, FavoriteEntity.entity_id == entity_id)
        return await session.scalar(stmt)

    async def create_favorite(self, session: AsyncSession, payload: dict) -> FavoriteEntity:
        item = FavoriteEntity(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def delete_favorite(self, session: AsyncSession, favorite: FavoriteEntity) -> None:
        await session.delete(favorite)
        await session.commit()

    async def list_subscriptions(self, session: AsyncSession, user_id: int) -> list[NotificationSubscription]:
        stmt = select(NotificationSubscription).where(NotificationSubscription.user_id == user_id).order_by(NotificationSubscription.id.asc())
        return list((await session.scalars(stmt)).all())

    async def get_subscription(self, session: AsyncSession, subscription_id: int, user_id: int) -> NotificationSubscription | None:
        stmt = select(NotificationSubscription).where(NotificationSubscription.id == subscription_id, NotificationSubscription.user_id == user_id)
        return await session.scalar(stmt)

    async def find_subscription(self, session: AsyncSession, user_id: int, entity_type: str, entity_id: int) -> NotificationSubscription | None:
        stmt = select(NotificationSubscription).where(NotificationSubscription.user_id == user_id, NotificationSubscription.entity_type == entity_type, NotificationSubscription.entity_id == entity_id)
        return await session.scalar(stmt)

    async def list_matching_subscriptions(self, session: AsyncSession, *, entities: list[tuple[str, int]], notification_type: str) -> list[NotificationSubscription]:
        if not entities:
            return []
        conditions = [and_(NotificationSubscription.entity_type == entity_type, NotificationSubscription.entity_id == entity_id) for entity_type, entity_id in entities]
        stmt = select(NotificationSubscription).where(NotificationSubscription.is_active.is_(True), or_(*conditions)).order_by(NotificationSubscription.id.asc())
        items = list((await session.scalars(stmt)).all())
        matched: list[NotificationSubscription] = []
        for item in items:
            types = list(item.notification_types or [])
            if not types or notification_type in types:
                matched.append(item)
        return matched

    async def create_subscription(self, session: AsyncSession, payload: dict) -> NotificationSubscription:
        item = NotificationSubscription(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def update_subscription(self, session: AsyncSession, subscription: NotificationSubscription, payload: dict) -> NotificationSubscription:
        for key, value in payload.items():
            setattr(subscription, key, value)
        await session.commit()
        await session.refresh(subscription)
        return subscription

    async def delete_subscription(self, session: AsyncSession, subscription: NotificationSubscription) -> None:
        await session.delete(subscription)
        await session.commit()

    async def list_notifications(self, session: AsyncSession, user_id: int) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc(), Notification.id.desc())
        return list((await session.scalars(stmt)).all())

    async def get_notification(self, session: AsyncSession, notification_id: int, user_id: int) -> Notification | None:
        stmt = select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        return await session.scalar(stmt)

    async def count_unread_notifications(self, session: AsyncSession, user_id: int) -> int:
        stmt = select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.status == 'unread')
        return int((await session.scalar(stmt)) or 0)

    async def mark_notification_read(self, session: AsyncSession, notification: Notification, now: datetime) -> Notification:
        notification.status = 'read'
        notification.read_at = now
        await session.commit()
        await session.refresh(notification)
        return notification

    async def mark_all_notifications_read(self, session: AsyncSession, user_id: int, now: datetime) -> None:
        await session.execute(update(Notification).where(Notification.user_id == user_id, Notification.status == 'unread').values(status='read', read_at=now))
        await session.commit()

    async def create_notification(self, session: AsyncSession, payload: dict) -> Notification:
        item = Notification(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def find_duplicate_notification(self, session: AsyncSession, *, user_id: int, type_: str, title: str, entity_type: str | None, entity_id: int | None) -> Notification | None:
        notifications = await self.list_notifications(session, user_id)
        for item in notifications:
            if item.type != type_ or item.title != title:
                continue
            payload = item.payload_json or {}
            if payload.get('entity_type') == entity_type and payload.get('entity_id') == entity_id:
                return item
        return None
