from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin, TimestampMixin


class RankingSnapshot(Base, IdIntPkMixin, TimestampMixin):
    __tablename__ = "ranking_snapshots"

    ranking_type: Mapped[str] = mapped_column(String(32), index=True)
    ranking_date: Mapped[str] = mapped_column(String(16), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    rank_position: Mapped[int] = mapped_column(Integer(), index=True)
    points: Mapped[int] = mapped_column(Integer())
    movement: Mapped[int] = mapped_column(Integer(), default=0)
