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
    is_email_verified: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None
    locale: str | None = None
    timezone: str | None = None


class UserPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UserTokenBundle(BaseModel):
    access_token: str
    refresh_token: str
    user: UserProfile


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
