from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import NewsCategory, Notification, RankingSnapshot, Tag, User


class AdminSupportRepository:
    async def list_categories(self, session: AsyncSession) -> list[NewsCategory]:
        stmt = select(NewsCategory).order_by(NewsCategory.name.asc())
        return list((await session.scalars(stmt)).all())

    async def create_category(self, session: AsyncSession, payload: dict) -> NewsCategory:
        item = NewsCategory(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def get_category(self, session: AsyncSession, category_id: int) -> NewsCategory | None:
        return await session.get(NewsCategory, category_id)

    async def update_category(self, session: AsyncSession, item: NewsCategory, payload: dict) -> NewsCategory:
        for key, value in payload.items():
            setattr(item, key, value)
        await session.commit()
        await session.refresh(item)
        return item

    async def delete_category(self, session: AsyncSession, item: NewsCategory) -> None:
        await session.delete(item)
        await session.commit()

    async def list_tags(self, session: AsyncSession) -> list[Tag]:
        stmt = select(Tag).order_by(Tag.name.asc())
        return list((await session.scalars(stmt)).all())

    async def create_tag(self, session: AsyncSession, payload: dict) -> Tag:
        item = Tag(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def get_tag(self, session: AsyncSession, tag_id: int) -> Tag | None:
        return await session.get(Tag, tag_id)

    async def update_tag(self, session: AsyncSession, item: Tag, payload: dict) -> Tag:
        for key, value in payload.items():
            setattr(item, key, value)
        await session.commit()
        await session.refresh(item)
        return item

    async def delete_tag(self, session: AsyncSession, item: Tag) -> None:
        await session.delete(item)
        await session.commit()

    async def list_notifications(self, session: AsyncSession) -> list[Notification]:
        stmt = select(Notification).order_by(Notification.created_at.desc())
        return list((await session.scalars(stmt)).all())

    async def create_notification(self, session: AsyncSession, payload: dict) -> Notification:
        item = Notification(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def get_first_active_user(self, session: AsyncSession) -> User | None:
        stmt = select(User).where(User.status == 'active').order_by(User.id.asc())
        return await session.scalar(stmt)

    async def list_ranking_snapshots(self, session: AsyncSession) -> list[RankingSnapshot]:
        stmt = select(RankingSnapshot).order_by(RankingSnapshot.ranking_date.desc(), RankingSnapshot.rank_position.asc())
        return list((await session.scalars(stmt)).all())

    async def get_latest_ranking_type(self, session: AsyncSession) -> str | None:
        stmt = select(RankingSnapshot.ranking_type).order_by(RankingSnapshot.ranking_date.desc()).limit(1)
        return await session.scalar(stmt)

    async def count_rankings_for_date(self, session: AsyncSession, ranking_type: str, ranking_date: str) -> int:
        stmt = select(func.count()).select_from(RankingSnapshot).where(RankingSnapshot.ranking_type == ranking_type, RankingSnapshot.ranking_date == ranking_date)
        return int((await session.scalar(stmt)) or 0)
