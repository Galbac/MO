from __future__ import annotations

from datetime import date

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import Match, MatchEvent, NewsArticle, Player, RankingSnapshot, Tournament


class DiscoveryRepository:
    @staticmethod
    def _query_variants(query: str) -> list[str]:
        normalized = ' '.join(query.lower().replace('-', ' ').replace('_', ' ').split())
        compact = normalized.replace(' ', '')
        variants = [normalized]
        if compact and compact != normalized:
            variants.append(compact)
        if normalized.endswith('s') and len(normalized) > 4:
            variants.append(normalized[:-1])
        return [item for item in variants if item]

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

    async def list_rankings_for_player(self, session: AsyncSession, *, player_id: int) -> list[RankingSnapshot]:
        stmt = (
            select(RankingSnapshot)
            .where(RankingSnapshot.player_id == player_id)
            .order_by(RankingSnapshot.ranking_date.desc(), RankingSnapshot.ranking_type.asc())
        )
        return list((await session.scalars(stmt)).all())

    async def list_finished_matches_for_season(self, session: AsyncSession, *, season_year: int) -> list[tuple[Match, Tournament]]:
        stmt = (
            select(Match, Tournament)
            .join(Tournament, Tournament.id == Match.tournament_id)
            .where(
                Tournament.season_year == season_year,
                Match.status.in_(["finished", "retired", "walkover"]),
                Match.winner_id.is_not(None),
            )
            .order_by(Match.scheduled_at.desc(), Match.id.desc())
        )
        return list((await session.execute(stmt)).all())

    async def search_players(self, session: AsyncSession, query: str, *, limit: int = 5) -> list[Player]:
        variants = self._query_variants(query)
        conditions = []
        rank_cases = []
        for item in variants:
            like_value = f'%{item}%'
            conditions.append(or_(Player.full_name.ilike(like_value), Player.first_name.ilike(like_value), Player.last_name.ilike(like_value), Player.slug.ilike(like_value)))
            rank_cases.append((func.lower(Player.full_name) == item, 0))
            rank_cases.append((Player.slug.ilike(f'{item}%'), 1))
            rank_cases.append((Player.full_name.ilike(f'{item}%'), 2))
        stmt = select(Player).where(or_(*conditions)).order_by(case(*rank_cases, else_=3), Player.current_rank.asc().nullslast(), Player.full_name.asc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def search_tournaments(self, session: AsyncSession, query: str, *, limit: int = 5) -> list[Tournament]:
        variants = self._query_variants(query)
        conditions = []
        rank_cases = []
        for item in variants:
            like_value = f'%{item}%'
            conditions.append(or_(Tournament.name.ilike(like_value), Tournament.short_name.ilike(like_value), Tournament.slug.ilike(like_value), Tournament.city.ilike(like_value)))
            rank_cases.append((func.lower(Tournament.name) == item, 0))
            rank_cases.append((Tournament.slug.ilike(f'{item}%'), 1))
            rank_cases.append((Tournament.name.ilike(f'{item}%'), 2))
        stmt = select(Tournament).where(or_(*conditions)).order_by(case(*rank_cases, else_=3), Tournament.start_date.desc().nullslast(), Tournament.name.asc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def search_news(self, session: AsyncSession, query: str, *, limit: int = 5) -> list[NewsArticle]:
        variants = self._query_variants(query)
        conditions = []
        rank_cases = []
        for item in variants:
            like_value = f'%{item}%'
            conditions.append(or_(NewsArticle.title.ilike(like_value), NewsArticle.subtitle.ilike(like_value), NewsArticle.lead.ilike(like_value), NewsArticle.content_html.ilike(like_value), NewsArticle.slug.ilike(like_value)))
            rank_cases.append((func.lower(NewsArticle.title) == item, 0))
            rank_cases.append((NewsArticle.slug.ilike(f'{item}%'), 1))
            rank_cases.append((NewsArticle.title.ilike(f'{item}%'), 2))
        stmt = select(NewsArticle).where(or_(*conditions)).order_by(case(*rank_cases, else_=3), NewsArticle.published_at.desc().nullslast(), NewsArticle.id.desc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def search_matches(self, session: AsyncSession, query: str, *, limit: int = 5) -> list[Match]:
        variants = self._query_variants(query)
        conditions = []
        rank_cases = []
        for item in variants:
            like_value = f'%{item}%'
            conditions.append(or_(Match.slug.ilike(like_value), Match.score_summary.ilike(like_value), Match.round_code.ilike(like_value)))
            rank_cases.append((Match.slug.ilike(f'{item}%'), 0))
            rank_cases.append((Match.round_code.ilike(f'{item}%'), 1))
        stmt = select(Match).where(or_(*conditions)).order_by(case(*rank_cases, else_=2), Match.scheduled_at.desc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def list_live_matches(self, session: AsyncSession, *, today: date) -> list[Match]:
        stmt = select(Match).where(or_(Match.status.in_(['live', 'about_to_start']), ((Match.status == 'scheduled') & (func.date(Match.scheduled_at) == today.isoformat())))).order_by(Match.scheduled_at.asc())
        return list((await session.scalars(stmt)).all())

    async def list_live_events(self, session: AsyncSession, *, limit: int = 50) -> list[MatchEvent]:
        stmt = select(MatchEvent).order_by(MatchEvent.created_at.desc()).limit(limit)
        return list(reversed(list((await session.scalars(stmt)).all())))
