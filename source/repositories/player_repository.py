from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import HeadToHead, Match, NewsArticle, Player, RankingSnapshot


class PlayerRepository:
    async def create(self, session: AsyncSession, payload: dict) -> Player:
        item = Player(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def update(self, session: AsyncSession, player: Player, payload: dict) -> Player:
        for key, value in payload.items():
            setattr(player, key, value)
        await session.commit()
        await session.refresh(player)
        return player

    async def delete(self, session: AsyncSession, player: Player) -> None:
        await session.delete(player)
        await session.commit()

    async def list(self, session: AsyncSession, *, search: str | None, country_code: str | None, hand: str | None, status: str | None, rank_from: int | None, rank_to: int | None, page: int, per_page: int) -> tuple[list[Player], int]:
        stmt = select(Player)
        count_stmt = select(func.count()).select_from(Player)

        filters = []
        if search:
            filters.append(or_(Player.full_name.ilike(f"%{search}%"), Player.last_name.ilike(f"%{search}%")))
        if country_code:
            filters.append(Player.country_code == country_code)
        if hand:
            filters.append(Player.hand == hand)
        if status:
            filters.append(Player.status == status)
        if rank_from is not None:
            filters.append(Player.current_rank >= rank_from)
        if rank_to is not None:
            filters.append(Player.current_rank <= rank_to)
        for condition in filters:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        stmt = stmt.order_by(Player.current_rank.asc().nullslast(), Player.full_name.asc()).offset((page - 1) * per_page).limit(per_page)
        items = list((await session.scalars(stmt)).all())
        total = int((await session.scalar(count_stmt)) or 0)
        return items, total

    async def get(self, session: AsyncSession, player_id: int) -> Player | None:
        return await session.get(Player, player_id)

    async def get_matches(self, session: AsyncSession, player_id: int) -> list[Match]:
        stmt = select(Match).where(or_(Match.player1_id == player_id, Match.player2_id == player_id)).order_by(Match.scheduled_at.desc())
        return list((await session.scalars(stmt)).all())

    async def get_ranking_history(self, session: AsyncSession, player_id: int) -> list[RankingSnapshot]:
        stmt = select(RankingSnapshot).where(RankingSnapshot.player_id == player_id).order_by(RankingSnapshot.ranking_date.asc())
        return list((await session.scalars(stmt)).all())

    async def get_h2h(self, session: AsyncSession, player1_id: int, player2_id: int) -> HeadToHead | None:
        left, right = sorted((player1_id, player2_id))
        stmt = select(HeadToHead).where(HeadToHead.player1_id == left, HeadToHead.player2_id == right)
        return await session.scalar(stmt)

    async def get_news(self, session: AsyncSession, limit: int = 5) -> list[NewsArticle]:
        stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(limit)
        return list((await session.scalars(stmt)).all())
