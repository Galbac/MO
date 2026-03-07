from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import and_, func, or_, select
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

    async def list(
        self,
        session: AsyncSession,
        *,
        page: int,
        per_page: int,
        status: str | None,
        tournament_id: int | None = None,
        player_id: int | None = None,
        round_code: str | None = None,
        search: str | None = None,
        date_from: date | datetime | None = None,
        date_to: date | datetime | None = None,
    ) -> tuple[list[Match], int]:
        stmt = select(Match)
        count_stmt = select(func.count()).select_from(Match)
        filters = []
        if status:
            filters.append(Match.status == status)
        if tournament_id is not None:
            filters.append(Match.tournament_id == tournament_id)
        if player_id is not None:
            filters.append(or_(Match.player1_id == player_id, Match.player2_id == player_id))
        if round_code:
            filters.append(Match.round_code == round_code)
        if search:
            filters.append(func.lower(Match.slug).like(f"%{search.strip().lower()}%"))
        if date_from:
            start_value = date_from if isinstance(date_from, datetime) else datetime.combine(date_from, time.min)
            filters.append(Match.scheduled_at >= start_value)
        if date_to:
            end_value = date_to if isinstance(date_to, datetime) else datetime.combine(date_to, time.max)
            filters.append(Match.scheduled_at <= end_value)
        if filters:
            stmt = stmt.where(and_(*filters))
            count_stmt = count_stmt.where(and_(*filters))
        stmt = stmt.order_by(Match.scheduled_at.desc()).offset((page - 1) * per_page).limit(per_page)
        items = list((await session.scalars(stmt)).all())
        total = int((await session.scalar(count_stmt)) or 0)
        return items, total

    async def get(self, session: AsyncSession, match_id: int) -> Match | None:
        return await session.get(Match, match_id)

    async def get_by_slug(self, session: AsyncSession, slug: str) -> Match | None:
        stmt = select(Match).where(Match.slug == slug)
        return await session.scalar(stmt)

    async def find_event_by_provider_key(self, session: AsyncSession, *, match_id: int, provider_event_key: str) -> MatchEvent | None:
        events = await self.get_events(session, match_id)
        for item in events:
            payload = item.payload_json or {}
            if payload.get('provider_event_key') == provider_event_key:
                return item
        return None

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
        allowed_keys = {
            'player1_aces',
            'player2_aces',
            'player1_double_faults',
            'player2_double_faults',
            'player1_first_serve_pct',
            'player2_first_serve_pct',
            'player1_break_points_saved',
            'player2_break_points_saved',
            'duration_minutes',
        }
        normalized_payload = {key: value for key, value in payload.items() if key in allowed_keys}
        stats = await self.get_stats(session, match_id)
        if stats is None:
            stats = MatchStats(match_id=match_id, **normalized_payload)
            session.add(stats)
        else:
            for key, value in normalized_payload.items():
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

    async def upsert_h2h(self, session: AsyncSession, *, player1_id: int, player2_id: int, winner_id: int, surface: str | None, match_id: int) -> HeadToHead:
        left, right = sorted((player1_id, player2_id))
        record = await self.get_h2h(session, player1_id, player2_id)
        if record is None:
            record = HeadToHead(
                player1_id=left,
                player2_id=right,
                total_matches=0,
                player1_wins=0,
                player2_wins=0,
                hard_player1_wins=0,
                hard_player2_wins=0,
                clay_player1_wins=0,
                clay_player2_wins=0,
                grass_player1_wins=0,
                grass_player2_wins=0,
                last_match_id=None,
            )
            session.add(record)
            await session.flush()
        if record.last_match_id == match_id:
            await session.commit()
            await session.refresh(record)
            return record

        record.total_matches += 1
        winner_is_left = winner_id == left
        if winner_is_left:
            record.player1_wins += 1
        else:
            record.player2_wins += 1

        if surface == 'hard':
            if winner_is_left:
                record.hard_player1_wins += 1
            else:
                record.hard_player2_wins += 1
        elif surface == 'clay':
            if winner_is_left:
                record.clay_player1_wins += 1
            else:
                record.clay_player2_wins += 1
        elif surface == 'grass':
            if winner_is_left:
                record.grass_player1_wins += 1
            else:
                record.grass_player2_wins += 1

        record.last_match_id = match_id
        await session.commit()
        await session.refresh(record)
        return record

    async def get_related_news(self, session: AsyncSession, limit: int = 2) -> list[NewsArticle]:
        stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def get_upcoming(self, session: AsyncSession) -> list[Match]:
        stmt = select(Match).where(Match.status.in_(["scheduled", "about_to_start", "live"])).order_by(Match.scheduled_at.asc())
        return list((await session.scalars(stmt)).all())

    async def get_results(self, session: AsyncSession) -> list[Match]:
        stmt = select(Match).where(Match.status.in_(["finished", "retired", "walkover"])).order_by(Match.scheduled_at.desc())
        return list((await session.scalars(stmt)).all())
