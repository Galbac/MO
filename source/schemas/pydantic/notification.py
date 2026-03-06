from datetime import datetime

from pydantic import BaseModel, Field


class NotificationItem(BaseModel):
    id: int
    type: str
    title: str
    body: str
    payload_json: dict = Field(default_factory=dict)
    status: str = "unread"
    read_at: datetime | None = None
    created_at: datetime


class NotificationUnreadCount(BaseModel):
    unread_count: int
