from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin


class MatchEvent(Base, IdIntPkMixin):
    __tablename__ = "match_events"

    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    set_number: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    game_number: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
