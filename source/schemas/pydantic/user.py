from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserProfile(BaseModel):
    id: int
    email: EmailStr
    username: str
    role: str
    status: str = "active"
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None
    locale: str
    timezone: str
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    is_email_verified: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None
    locale: str | None = None
    timezone: str | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None


class UserPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UserTokenBundle(BaseModel):
    access_token: str
    refresh_token: str
    user: UserProfile
    token_type: str = "Bearer"
    access_expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None
    refresh_token_id: str | None = None


class FavoriteItem(BaseModel):
    id: int
    user_id: int
    entity_type: str
    entity_id: int
    entity_name: str


class FavoriteCreateRequest(BaseModel):
    entity_type: str
    entity_id: int


class NotificationSubscriptionItem(BaseModel):
    id: int
    user_id: int
    entity_type: str
    entity_id: int
    notification_types: list[str]
    channels: list[str]
    is_active: bool = True


class NotificationSubscriptionCreateRequest(BaseModel):
    entity_type: str
    entity_id: int
    notification_types: list[str]
    channels: list[str]


class NotificationSubscriptionUpdateRequest(BaseModel):
    notification_types: list[str] | None = None
    channels: list[str] | None = None
    is_active: bool | None = None


class MatchReminderItem(BaseModel):
    id: int
    user_id: int
    match_id: int
    match_slug: str
    title: str
    tournament_name: str
    scheduled_at: datetime
    remind_before_minutes: int = 30
    channel: str = "web"
    is_active: bool = True
    reminder_at: datetime | None = None
    source: str = "manual"


class MatchReminderCreateRequest(BaseModel):
    match_id: int
    remind_before_minutes: int = Field(default=30, ge=5, le=1440)
    channel: str = "web"


class MatchReminderUpdateRequest(BaseModel):
    remind_before_minutes: int | None = Field(default=None, ge=5, le=1440)
    channel: str | None = None
    is_active: bool | None = None


class UserCalendarOverview(BaseModel):
    items: list[MatchReminderItem] = Field(default_factory=list)
    total: int = 0
    active: int = 0
    next_item_at: datetime | None = None


class SmartFeedBundle(BaseModel):
    players: list[dict] = Field(default_factory=list)
    tournaments: list[dict] = Field(default_factory=list)
    matches: list[dict] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class PushSubscriptionItem(BaseModel):
    id: int
    user_id: int
    endpoint: str
    device_label: str | None = None
    permission: str = "default"
    is_active: bool = True
    created_at: datetime | None = None


class PushSubscriptionCreateRequest(BaseModel):
    endpoint: str
    device_label: str | None = None
    keys_json: dict = Field(default_factory=dict)
    permission: str = "granted"


class PushSubscriptionTestRequest(BaseModel):
    title: str = "Тестовое браузерное уведомление"
    body: str = "Браузерные уведомления для портала включены."
