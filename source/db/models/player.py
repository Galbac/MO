from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin, TimestampMixin


class Player(Base, IdIntPkMixin, TimestampMixin):
    __tablename__ = "players"

    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(120), index=True)
    last_name: Mapped[str] = mapped_column(String(120), index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    country_code: Mapped[str] = mapped_column(String(8), index=True)
    country_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    birth_date: Mapped[Date | None] = mapped_column(Date(), nullable=True)
    height_cm: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    weight_kg: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    hand: Mapped[str | None] = mapped_column(String(32), nullable=True)
    backhand: Mapped[str | None] = mapped_column(String(32), nullable=True)
    biography: Mapped[str | None] = mapped_column(Text(), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    current_rank: Mapped[int | None] = mapped_column(Integer(), nullable=True, index=True)
    current_points: Mapped[int | None] = mapped_column(Integer(), nullable=True)
