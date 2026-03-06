from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin, TimestampMixin


class Match(Base, IdIntPkMixin, TimestampMixin):
    __tablename__ = "matches"

    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), index=True)
    round_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    best_of_sets: Mapped[int] = mapped_column(Integer(), default=3)
    player1_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    player2_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actual_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    court_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    score_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retire_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    walkover_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
