from datetime import datetime

from pydantic import BaseModel, EmailStr


class AdminUserItem(BaseModel):
    id: int
    email: EmailStr
    username: str
    role: str
    status: str
    created_at: datetime


class AdminIntegrationItem(BaseModel):
    provider: str
    status: str
    last_sync_at: datetime | None = None
    last_error: str | None = None


class AdminIntegrationLogItem(BaseModel):
    timestamp: datetime
    level: str
    message: str


class AdminJobItem(BaseModel):
    id: int
    job_type: str
    status: str
    payload: dict
    result: dict | None = None
    run_at: datetime
    created_at: datetime
    updated_at: datetime
    attempts: int
    error: str | None = None


class AdminJobPruneResult(BaseModel):
    removed: int


class AdminMaintenanceArtifact(BaseModel):
    code: str
    exists: bool
    updated_at: datetime | None = None
    path: str


class AdminMaintenanceRunResult(BaseModel):
    job_id: int
    job_type: str


class AuditLogItem(BaseModel):
    id: int
    user_id: int | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    before_json: dict | None = None
    after_json: dict | None = None
    created_at: datetime


class AdminNotificationTemplate(BaseModel):
    id: int
    code: str
    title: str
    channel: str
    is_active: bool
    updated_at: datetime


class AdminNotificationBroadcast(BaseModel):
    id: int
    title: str
    status: str
    sent_count: int
    created_at: datetime
