from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin, TimestampMixin


class MatchReminder(Base, IdIntPkMixin, TimestampMixin):
    __tablename__ = "match_reminders"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    remind_before_minutes: Mapped[int] = mapped_column(Integer(), default=30)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
    channel: Mapped[str] = mapped_column(String(32), default="web", index=True)


class PushSubscription(Base, IdIntPkMixin, TimestampMixin):
    __tablename__ = "push_subscriptions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    endpoint: Mapped[str] = mapped_column(String(1024), unique=True)
    device_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    keys_json: Mapped[dict] = mapped_column(JSON(), default=dict)
    permission: Mapped[str] = mapped_column(String(32), default="default", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
