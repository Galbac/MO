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


class AdminIntegrationUpdateResult(BaseModel):
    provider: str
    status: str
    last_sync_at: datetime | None = None
    last_error: str | None = None
    settings: dict


class AdminIntegrationSyncResult(BaseModel):
    provider: str
    status: str
    last_sync_at: datetime | None = None
    last_error: str | None = None
    message: str
    applied_count: int = 0
    logs_count: int = 0


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
    remaining: int
    statuses: list[str]


class AdminJobProcessResult(BaseModel):
    processed: int
    failed: int
    skipped: int
    processed_job_ids: list[int]
    failed_job_ids: list[int]


class AdminMaintenanceArtifact(BaseModel):
    code: str
    exists: bool
    updated_at: datetime | None = None
    path: str


class AdminMaintenanceRunResult(BaseModel):
    job_id: int
    job_type: str
    status: str
    result: dict | None = None
    error: str | None = None


class AuditLogItem(BaseModel):
    id: int
    user_id: int | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    before_json: dict | None = None
    after_json: dict | None = None
    changed_keys: list[str] = []
    changed_fields_count: int = 0
    created_at: datetime


class AuditLogSummary(BaseModel):
    total: int
    by_action: dict[str, int]
    by_entity_type: dict[str, int]
    latest_at: datetime | None = None


class AdminNotificationTemplate(BaseModel):
    id: int
    code: str
    title: str
    channel: str
    is_active: bool
    updated_at: datetime


class AdminNotificationBroadcast(BaseModel):
    id: int
    code: str
    title: str
    status: str
    sent_count: int
    created_at: datetime
    last_delivery_at: datetime | None = None
    last_reason: str | None = None
    channels: list[str]
    delivery_stats: dict[str, int]


class AdminNotificationDeliveryLogItem(BaseModel):
    user_id: int
    channel: str
    notification_type: str
    title: str
    entity_type: str
    entity_id: int
    status: str
    reason: str | None = None
    created_at: datetime
