from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import Match, MatchEvent, NewsArticle, Player, RankingSnapshot, Tournament


class DiscoveryRepository:
    async def list_rankings(self, session: AsyncSession, *, ranking_type: str | None = None, ranking_date: str | None = None) -> list[RankingSnapshot]:
        stmt = select(RankingSnapshot)
        if ranking_type:
            stmt = stmt.where(RankingSnapshot.ranking_type == ranking_type)
        if ranking_date:
            stmt = stmt.where(RankingSnapshot.ranking_date == ranking_date)
        stmt = stmt.order_by(RankingSnapshot.rank_position.asc(), RankingSnapshot.player_id.asc())
        return list((await session.scalars(stmt)).all())

    async def list_ranking_dates(self, session: AsyncSession, *, ranking_type: str | None = None) -> list[str]:
        stmt = select(RankingSnapshot.ranking_date)
        if ranking_type:
            stmt = stmt.where(RankingSnapshot.ranking_type == ranking_type)
        stmt = stmt.distinct().order_by(RankingSnapshot.ranking_date.desc())
        return [item for item in (await session.scalars(stmt)).all()]

    async def list_players_by_ids(self, session: AsyncSession, player_ids: list[int]) -> list[Player]:
        if not player_ids:
            return []
        stmt = select(Player).where(Player.id.in_(player_ids))
        return list((await session.scalars(stmt)).all())

    async def search_players(self, session: AsyncSession, query: str, *, limit: int = 5) -> list[Player]:
        stmt = select(Player).where(or_(Player.full_name.ilike(f'%{query}%'), Player.first_name.ilike(f'%{query}%'), Player.last_name.ilike(f'%{query}%'), Player.slug.ilike(f'%{query}%'))).order_by(Player.current_rank.asc().nullslast(), Player.full_name.asc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def search_tournaments(self, session: AsyncSession, query: str, *, limit: int = 5) -> list[Tournament]:
        stmt = select(Tournament).where(or_(Tournament.name.ilike(f'%{query}%'), Tournament.short_name.ilike(f'%{query}%'), Tournament.slug.ilike(f'%{query}%'), Tournament.city.ilike(f'%{query}%'))).order_by(Tournament.start_date.desc().nullslast(), Tournament.name.asc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def search_news(self, session: AsyncSession, query: str, *, limit: int = 5) -> list[NewsArticle]:
        stmt = select(NewsArticle).where(or_(NewsArticle.title.ilike(f'%{query}%'), NewsArticle.subtitle.ilike(f'%{query}%'), NewsArticle.lead.ilike(f'%{query}%'), NewsArticle.content_html.ilike(f'%{query}%'), NewsArticle.slug.ilike(f'%{query}%'))).order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.id.desc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def search_matches(self, session: AsyncSession, query: str, *, limit: int = 5) -> list[Match]:
        stmt = select(Match).where(or_(Match.slug.ilike(f'%{query}%'), Match.score_summary.ilike(f'%{query}%'), Match.round_code.ilike(f'%{query}%'))).order_by(Match.scheduled_at.desc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def list_live_matches(self, session: AsyncSession, *, today: date) -> list[Match]:
        stmt = select(Match).where(or_(Match.status.in_(['live', 'about_to_start']), ((Match.status == 'scheduled') & (func.date(Match.scheduled_at) == today.isoformat())))).order_by(Match.scheduled_at.asc())
        return list((await session.scalars(stmt)).all())

    async def list_live_events(self, session: AsyncSession, *, limit: int = 50) -> list[MatchEvent]:
        stmt = select(MatchEvent).order_by(MatchEvent.created_at.desc()).limit(limit)
        return list(reversed(list((await session.scalars(stmt)).all())))
