from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import Match, Tournament


class TournamentRepository:
    async def create(self, session: AsyncSession, payload: dict) -> Tournament:
        item = Tournament(**payload)
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def update(self, session: AsyncSession, tournament: Tournament, payload: dict) -> Tournament:
        for key, value in payload.items():
            setattr(tournament, key, value)
        await session.commit()
        await session.refresh(tournament)
        return tournament

    async def delete(self, session: AsyncSession, tournament: Tournament) -> None:
        await session.delete(tournament)
        await session.commit()

    async def list(
        self,
        session: AsyncSession,
        *,
        page: int,
        per_page: int,
        search: str | None = None,
        category: str | None = None,
        surface: str | None = None,
        status: str | None = None,
        season_year: int | None = None,
    ) -> tuple[list[Tournament], int]:
        stmt = select(Tournament)
        count_stmt = select(func.count()).select_from(Tournament)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(or_(func.lower(Tournament.name).like(pattern), func.lower(Tournament.slug).like(pattern), func.lower(Tournament.city).like(pattern)))
            count_stmt = count_stmt.where(or_(func.lower(Tournament.name).like(pattern), func.lower(Tournament.slug).like(pattern), func.lower(Tournament.city).like(pattern)))
        if category:
            stmt = stmt.where(Tournament.category == category)
            count_stmt = count_stmt.where(Tournament.category == category)
        if surface:
            stmt = stmt.where(Tournament.surface == surface)
            count_stmt = count_stmt.where(Tournament.surface == surface)
        if status:
            stmt = stmt.where(Tournament.status == status)
            count_stmt = count_stmt.where(Tournament.status == status)
        if season_year is not None:
            stmt = stmt.where(Tournament.season_year == season_year)
            count_stmt = count_stmt.where(Tournament.season_year == season_year)
        stmt = stmt.order_by(Tournament.start_date.desc().nullslast(), Tournament.name.asc()).offset((page - 1) * per_page).limit(per_page)
        items = list((await session.scalars(stmt)).all())
        total = int((await session.scalar(count_stmt)) or 0)
        return items, total

    async def get(self, session: AsyncSession, tournament_id: int) -> Tournament | None:
        return await session.get(Tournament, tournament_id)

    async def get_matches(self, session: AsyncSession, tournament_id: int) -> list[Match]:
        stmt = select(Match).where(Match.tournament_id == tournament_id).order_by(Match.scheduled_at.asc())
        return list((await session.scalars(stmt)).all())
