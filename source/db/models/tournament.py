from sqlalchemy import Boolean, Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin, TimestampMixin


class Tournament(Base, IdIntPkMixin, TimestampMixin):
    __tablename__ = "tournaments"

    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    short_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    surface: Mapped[str] = mapped_column(String(32), index=True)
    indoor: Mapped[bool] = mapped_column(Boolean(), default=False)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    prize_money: Mapped[str | None] = mapped_column(String(120), nullable=True)
    points_winner: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    season_year: Mapped[int] = mapped_column(Integer(), index=True)
    start_date: Mapped[Date | None] = mapped_column(Date(), nullable=True, index=True)
    end_date: Mapped[Date | None] = mapped_column(Date(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled", index=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
