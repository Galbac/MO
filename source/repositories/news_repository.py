from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import NewsArticle, NewsCategory, Tag


class NewsRepository:
    async def create(self, session: AsyncSession, payload: dict) -> NewsArticle:
        item = NewsArticle(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def get(self, session: AsyncSession, news_id: int) -> NewsArticle | None:
        return await session.get(NewsArticle, news_id)

    async def update(self, session: AsyncSession, article: NewsArticle, payload: dict) -> NewsArticle:
        for key, value in payload.items():
            setattr(article, key, value)
        await session.commit()
        await session.refresh(article)
        return article

    async def delete(self, session: AsyncSession, article: NewsArticle) -> None:
        await session.delete(article)
        await session.commit()

    async def list(self, session: AsyncSession, *, page: int, per_page: int) -> tuple[list[NewsArticle], int]:
        stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.id.desc()).offset((page - 1) * per_page).limit(per_page)
        count_stmt = select(func.count()).select_from(NewsArticle)
        items = list((await session.scalars(stmt)).all())
        total = int((await session.scalar(count_stmt)) or 0)
        return items, total

    async def get_by_slug(self, session: AsyncSession, slug: str) -> NewsArticle | None:
        stmt = select(NewsArticle).where(NewsArticle.slug == slug)
        return await session.scalar(stmt)

    async def list_categories(self, session: AsyncSession) -> list[NewsCategory]:
        stmt = select(NewsCategory).order_by(NewsCategory.name.asc())
        return list((await session.scalars(stmt)).all())

    async def list_tags(self, session: AsyncSession) -> list[Tag]:
        stmt = select(Tag).order_by(Tag.name.asc())
        return list((await session.scalars(stmt)).all())

    async def list_featured(self, session: AsyncSession) -> list[NewsArticle]:
        stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc().nullslast()).limit(3)
        return list((await session.scalars(stmt)).all())

    async def list_related(self, session: AsyncSession, *, slug: str | None = None, limit: int = 2) -> list[NewsArticle]:
        stmt = select(NewsArticle)
        if slug:
            stmt = stmt.where(NewsArticle.slug != slug)
        stmt = stmt.order_by(NewsArticle.published_at.desc().nullslast()).limit(limit)
        return list((await session.scalars(stmt)).all())
