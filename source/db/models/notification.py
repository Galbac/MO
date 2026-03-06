from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin, TimestampMixin


class NotificationSubscription(Base, IdIntPkMixin):
    __tablename__ = "notification_subscriptions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(Integer(), index=True)
    notification_types: Mapped[dict] = mapped_column(JSON(), default=list)
    channels: Mapped[dict] = mapped_column(JSON(), default=list)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)


class Notification(Base, IdIntPkMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text())
    payload_json: Mapped[dict] = mapped_column(JSON(), default=dict)
    status: Mapped[str] = mapped_column(String(32), default="unread", index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
