from __future__ import annotations

from sqlalchemy import func, select
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

    async def list(self, session: AsyncSession, *, page: int, per_page: int) -> tuple[list[Tournament], int]:
        stmt = select(Tournament).order_by(Tournament.start_date.desc().nullslast(), Tournament.name.asc()).offset((page - 1) * per_page).limit(per_page)
        count_stmt = select(func.count()).select_from(Tournament)
        items = list((await session.scalars(stmt)).all())
        total = int((await session.scalar(count_stmt)) or 0)
        return items, total

    async def get(self, session: AsyncSession, tournament_id: int) -> Tournament | None:
        return await session.get(Tournament, tournament_id)

    async def get_matches(self, session: AsyncSession, tournament_id: int) -> list[Match]:
        stmt = select(Match).where(Match.tournament_id == tournament_id).order_by(Match.scheduled_at.asc())
        return list((await session.scalars(stmt)).all())
