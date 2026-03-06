from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import HeadToHead, Match, MatchEvent, MatchSet, MatchStats, NewsArticle


class MatchRepository:
    async def create(self, session: AsyncSession, payload: dict) -> Match:
        item = Match(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def update(self, session: AsyncSession, match: Match, payload: dict) -> Match:
        for key, value in payload.items():
            setattr(match, key, value)
        await session.commit()
        await session.refresh(match)
        return match

    async def delete(self, session: AsyncSession, match: Match) -> None:
        await session.delete(match)
        await session.commit()

    async def list(self, session: AsyncSession, *, page: int, per_page: int, status: str | None) -> tuple[list[Match], int]:
        stmt = select(Match)
        count_stmt = select(func.count()).select_from(Match)
        if status:
            stmt = stmt.where(Match.status == status)
            count_stmt = count_stmt.where(Match.status == status)
        stmt = stmt.order_by(Match.scheduled_at.desc()).offset((page - 1) * per_page).limit(per_page)
        items = list((await session.scalars(stmt)).all())
        total = int((await session.scalar(count_stmt)) or 0)
        return items, total

    async def get(self, session: AsyncSession, match_id: int) -> Match | None:
        return await session.get(Match, match_id)

    async def get_sets(self, session: AsyncSession, match_id: int) -> list[MatchSet]:
        stmt = select(MatchSet).where(MatchSet.match_id == match_id).order_by(MatchSet.set_number.asc())
        return list((await session.scalars(stmt)).all())

    async def replace_sets(self, session: AsyncSession, match_id: int, payload: list[dict]) -> list[MatchSet]:
        existing = await self.get_sets(session, match_id)
        for item in existing:
            await session.delete(item)
        for item in payload:
            session.add(MatchSet(match_id=match_id, **item))
        await session.commit()
        return await self.get_sets(session, match_id)

    async def get_stats(self, session: AsyncSession, match_id: int) -> MatchStats | None:
        stmt = select(MatchStats).where(MatchStats.match_id == match_id)
        return await session.scalar(stmt)

    async def upsert_stats(self, session: AsyncSession, match_id: int, payload: dict) -> MatchStats:
        stats = await self.get_stats(session, match_id)
        if stats is None:
            stats = MatchStats(match_id=match_id, **payload)
            session.add(stats)
        else:
            for key, value in payload.items():
                setattr(stats, key, value)
        await session.commit()
        await session.refresh(stats)
        return stats

    async def get_events(self, session: AsyncSession, match_id: int) -> list[MatchEvent]:
        stmt = select(MatchEvent).where(MatchEvent.match_id == match_id).order_by(MatchEvent.created_at.asc())
        return list((await session.scalars(stmt)).all())

    async def create_event(self, session: AsyncSession, payload: dict) -> MatchEvent:
        item = MatchEvent(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def get_h2h(self, session: AsyncSession, player1_id: int, player2_id: int) -> HeadToHead | None:
        left, right = sorted((player1_id, player2_id))
        stmt = select(HeadToHead).where(HeadToHead.player1_id == left, HeadToHead.player2_id == right)
        return await session.scalar(stmt)

    async def get_related_news(self, session: AsyncSession, limit: int = 2) -> list[NewsArticle]:
        stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def get_upcoming(self, session: AsyncSession) -> list[Match]:
        stmt = select(Match).where(Match.status.in_(["scheduled", "about_to_start", "live"])).order_by(Match.scheduled_at.asc())
        return list((await session.scalars(stmt)).all())

    async def get_results(self, session: AsyncSession) -> list[Match]:
        stmt = select(Match).where(Match.status.in_(["finished", "retired", "walkover"])).order_by(Match.scheduled_at.desc())
        return list((await session.scalars(stmt)).all())
