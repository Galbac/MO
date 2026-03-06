from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin


class MatchSet(Base, IdIntPkMixin):
    __tablename__ = "match_sets"

    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    set_number: Mapped[int] = mapped_column(Integer(), index=True)
    player1_games: Mapped[int] = mapped_column(Integer())
    player2_games: Mapped[int] = mapped_column(Integer())
    tiebreak_player1_points: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    tiebreak_player2_points: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    is_finished: Mapped[bool] = mapped_column(Boolean(), default=True)
