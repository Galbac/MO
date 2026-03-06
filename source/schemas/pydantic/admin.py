from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


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
    logs_count: int = 0


class AdminIntegrationLogItem(BaseModel):
    timestamp: datetime
    level: str
    message: str


class AdminIntegrationDetail(BaseModel):
    provider: str
    status: str
    last_sync_at: datetime | None = None
    last_error: str | None = None
    settings: dict = Field(default_factory=dict)
    logs_count: int = 0
    latest_log_at: datetime | None = None
    latest_log_level: str | None = None
    storage_backend: str
    storage_path: str


class AdminIntegrationLogSummary(BaseModel):
    provider: str
    total: int
    by_level: dict[str, int] = Field(default_factory=dict)
    latest_at: datetime | None = None


class AdminSystemLogItem(BaseModel):
    timestamp: datetime
    category: str
    level: str
    message: str
    context: dict


class AdminSystemLogSummary(BaseModel):
    total: int
    categories: list[str]
    by_level: dict[str, int] = Field(default_factory=dict)
    latest_at: datetime | None = None


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


class AdminIntegrationSummary(BaseModel):
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    with_errors: int = 0
    latest_sync_at: datetime | None = None
    providers: list[str] = Field(default_factory=list)


class AdminActionResult(BaseModel):
    entity_type: str
    action: str
    status: str
    entity_id: int | None = None
    message: str | None = None
    job_id: int | None = None
    scheduled_at: datetime | None = None
    details: dict = Field(default_factory=dict)


class AdminBulkImportResult(BaseModel):
    entity_type: str
    action: str
    status: str
    imported_count: int
    entity_ids: list[int]
    details: dict = Field(default_factory=dict)


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


class AdminJobSummary(BaseModel):
    total: int
    pending: int
    failed: int
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    latest_updated_at: datetime | None = None
    backend: str


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


class AdminRuntimeBackupItem(BaseModel):
    filename: str
    path: str
    size_bytes: int
    created_at: datetime


class AdminMediaItem(BaseModel):
    id: int
    filename: str
    content_type: str
    url: str
    size: int | None = None
    created_at: datetime | None = None
    exists: bool
    stored_path: str


class AdminMediaSummary(BaseModel):
    total: int
    total_size_bytes: int = 0
    missing_files: int = 0
    content_types: dict[str, int] = Field(default_factory=dict)
    latest_created_at: datetime | None = None
    storage_backend: str
    storage_path: str


class AdminSettingsPayload(BaseModel):
    values: dict = Field(default_factory=dict)
    storage_backend: str
    storage_path: str
    updated_at: datetime | None = None


class AuditLogItem(BaseModel):
    id: int
    user_id: int | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    before_json: dict | None = None
    after_json: dict | None = None
    changed_keys: list[str] = Field(default_factory=list)
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


class AdminNotificationSummary(BaseModel):
    total_templates: int
    total_broadcasts: int
    total_delivery_logs: int
    by_status: dict[str, int] = Field(default_factory=dict)
    by_channel: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    latest_delivery_at: datetime | None = None
