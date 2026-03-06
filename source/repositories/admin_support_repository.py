from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import NewsCategory, Notification, Player, RankingSnapshot, Tag, User


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


    async def list_ranking_types(self, session: AsyncSession) -> list[str]:
        stmt = select(RankingSnapshot.ranking_type).distinct().order_by(RankingSnapshot.ranking_type.asc())
        return [item for item in (await session.scalars(stmt)).all()]

    async def list_ranking_dates(self, session: AsyncSession, ranking_type: str) -> list[str]:
        stmt = select(RankingSnapshot.ranking_date).where(RankingSnapshot.ranking_type == ranking_type).distinct().order_by(RankingSnapshot.ranking_date.asc())
        return [item for item in (await session.scalars(stmt)).all()]

    async def list_rankings_for_date(self, session: AsyncSession, ranking_type: str, ranking_date: str) -> list[RankingSnapshot]:
        stmt = select(RankingSnapshot).where(RankingSnapshot.ranking_type == ranking_type, RankingSnapshot.ranking_date == ranking_date).order_by(RankingSnapshot.rank_position.asc(), RankingSnapshot.player_id.asc())
        return list((await session.scalars(stmt)).all())

    async def get_latest_ranking_type(self, session: AsyncSession) -> str | None:
        stmt = select(RankingSnapshot.ranking_type).order_by(RankingSnapshot.ranking_date.desc()).limit(1)
        return await session.scalar(stmt)

    async def count_rankings_for_date(self, session: AsyncSession, ranking_type: str, ranking_date: str) -> int:
        stmt = select(func.count()).select_from(RankingSnapshot).where(RankingSnapshot.ranking_type == ranking_type, RankingSnapshot.ranking_date == ranking_date)
        return int((await session.scalar(stmt)) or 0)

    async def find_players_by_names(self, session: AsyncSession, names: list[str]) -> list[Player]:
        if not names:
            return []
        stmt = select(Player).where(Player.full_name.in_(names))
        return list((await session.scalars(stmt)).all())

    async def get_previous_rankings(self, session: AsyncSession, ranking_type: str, ranking_date: str) -> list[RankingSnapshot]:
        previous_date_stmt = (
            select(RankingSnapshot.ranking_date)
            .where(RankingSnapshot.ranking_type == ranking_type, RankingSnapshot.ranking_date < ranking_date)
            .order_by(RankingSnapshot.ranking_date.desc())
            .limit(1)
        )
        previous_date = await session.scalar(previous_date_stmt)
        if previous_date is None:
            return []
        stmt = select(RankingSnapshot).where(RankingSnapshot.ranking_type == ranking_type, RankingSnapshot.ranking_date == previous_date)
        return list((await session.scalars(stmt)).all())

    async def replace_rankings(self, session: AsyncSession, *, ranking_type: str, ranking_date: str, rows: list[dict]) -> list[RankingSnapshot]:
        await session.execute(delete(RankingSnapshot).where(RankingSnapshot.ranking_type == ranking_type, RankingSnapshot.ranking_date == ranking_date))
        items = [RankingSnapshot(**row) for row in rows]
        session.add_all(items)
        await session.flush()
        return items

    async def clear_player_current_rankings(self, session: AsyncSession, player_ids: list[int]) -> None:
        if not player_ids:
            return
        stmt = select(Player).where(Player.id.in_(player_ids))
        players = list((await session.scalars(stmt)).all())
        for player in players:
            player.current_rank = None
            player.current_points = None

    async def apply_player_current_rankings(self, session: AsyncSession, ranking_rows: list[dict]) -> None:
        if not ranking_rows:
            return
        player_ids = [int(row['player_id']) for row in ranking_rows]
        stmt = select(Player).where(Player.id.in_(player_ids))
        players = {item.id: item for item in list((await session.scalars(stmt)).all())}
        for row in ranking_rows:
            player = players.get(int(row['player_id']))
            if player is None:
                continue
            player.current_rank = int(row['rank_position'])
            player.current_points = int(row['points'])

    async def commit(self, session: AsyncSession) -> None:
        await session.commit()
