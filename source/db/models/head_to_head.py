from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin


class HeadToHead(Base, IdIntPkMixin):
    __tablename__ = "head_to_heads"

    player1_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    player2_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    total_matches: Mapped[int] = mapped_column(Integer(), default=0)
    player1_wins: Mapped[int] = mapped_column(Integer(), default=0)
    player2_wins: Mapped[int] = mapped_column(Integer(), default=0)
    hard_player1_wins: Mapped[int] = mapped_column(Integer(), default=0)
    hard_player2_wins: Mapped[int] = mapped_column(Integer(), default=0)
    clay_player1_wins: Mapped[int] = mapped_column(Integer(), default=0)
    clay_player2_wins: Mapped[int] = mapped_column(Integer(), default=0)
    grass_player1_wins: Mapped[int] = mapped_column(Integer(), default=0)
    grass_player2_wins: Mapped[int] = mapped_column(Integer(), default=0)
    last_match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), nullable=True, index=True)
