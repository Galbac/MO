from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin


class MatchStats(Base, IdIntPkMixin):
    __tablename__ = "match_stats"

    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), unique=True, index=True)
    player1_aces: Mapped[int] = mapped_column(Integer(), default=0)
    player2_aces: Mapped[int] = mapped_column(Integer(), default=0)
    player1_double_faults: Mapped[int] = mapped_column(Integer(), default=0)
    player2_double_faults: Mapped[int] = mapped_column(Integer(), default=0)
    player1_first_serve_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    player2_first_serve_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    player1_break_points_saved: Mapped[int] = mapped_column(Integer(), default=0)
    player2_break_points_saved: Mapped[int] = mapped_column(Integer(), default=0)
    duration_minutes: Mapped[int] = mapped_column(Integer(), default=0)
