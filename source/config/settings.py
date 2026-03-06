import os

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_postgres_url() -> str:
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    database = os.getenv('POSTGRES_DB', 'tennis_portal')
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', 'postgres')
    return f'postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}'



class RunConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    production: bool = False


class ProjectName(BaseModel):
    title: str = "Makhachkala Open"
    path: str = ""
    slug: str = "makhachkala_open"


class ApiV1Prefix(BaseModel):
    prefix: str = "/v1"


class ApiPrefix(BaseModel):
    prefix: str = "/api"
    v1: ApiV1Prefix = ApiV1Prefix()


class MiddlewareSettings(BaseModel):
    cors_origins: list[str] = ["http://localhost", "http://localhost:3000"]
    allow_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_headers: list[str] = ["Authorization", "Content-Type"]


class AuthSettings(BaseModel):
    secret_key: str = os.getenv("FASTAPI_CFG__AUTH__SECRET_KEY", "dev-secret-key-change-me")
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_minutes: int = 60 * 24 * 14
    password_reset_token_ttl_minutes: int = 30
    email_verification_token_ttl_minutes: int = 60 * 24
    refresh_token_rotation_enabled: bool = True
    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_seconds: int = 60
    brute_force_lockout_seconds: int = 300




class MediaSettings(BaseModel):
    allowed_content_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "text/plain",
    ]
    allowed_extensions_by_content_type: dict[str, list[str]] = {
        "image/jpeg": [".jpg", ".jpeg"],
        "image/png": [".png"],
        "image/webp": [".webp"],
        "image/gif": [".gif"],
        "text/plain": [".txt", ".log", ".md"],
    }
    forbidden_extensions: list[str] = [".html", ".htm", ".js", ".svg", ".exe", ".php", ".sh", ".bat"]
    max_upload_size_bytes: int = 1024 * 1024 * 5


class CacheSettings(BaseModel):
    enabled: bool = True
    storage_path: str = "var/cache_store.json"
    default_ttl_seconds: int = 300
    rankings_ttl_seconds: int = 600
    live_ttl_seconds: int = 15


class JobsSettings(BaseModel):
    enabled: bool = True
    storage_path: str = "var/job_queue.json"
    process_on_startup: bool = True
    poll_interval_seconds: int = 5


class RedisSettings(BaseModel):
    enabled: bool = False
    url: str = os.getenv("FASTAPI_CFG__REDIS__URL", "redis://localhost:6379/0")
    key_prefix: str = "tennis-portal"
    connect_timeout_seconds: float = 0.2
    state_fallback_path: str = "var/runtime_state"


class DocsSettings(BaseModel):
    username: str = os.getenv("FASTAPI_CFG__DOCS__USERNAME", "admin")
    password: str = os.getenv("FASTAPI_CFG__DOCS__PASSWORD", "admin")


class DbSettings(BaseModel):
    url: str = os.getenv(
        "FASTAPI_CFG__DB__URL",
        _default_postgres_url(),
    )
    auto_create: bool = True
    seed_demo_data: bool = True


class SecuritySettings(BaseModel):
    api_rate_limit_enabled: bool = True
    api_rate_limit_requests: int = 240
    api_rate_limit_window_seconds: int = 60


class NotificationSettings(BaseModel):
    allowed_types: list[str] = [
        "match_start",
        "match_soon",
        "set_finished",
        "match_finished",
        "news",
        "ranking_change",
        "tournament_start",
        "test",
    ]
    allowed_channels: list[str] = ["web", "email", "push"]
    active_channels: list[str] = ["web"]
    delivery_log_path: str = "var/notifications/delivery_log.json"


class MaintenanceSettings(BaseModel):
    artifacts_dir: str = "var/maintenance"
    backups_dir: str = "var/backups"



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.template", ".env"),
        case_sensitive=False,
        env_nested_delimiter="__",
        env_prefix="FASTAPI_CFG__",
        extra="ignore",
    )
    run: RunConfig = RunConfig()
    names: ProjectName = ProjectName()
    api: ApiPrefix = ApiPrefix()
    middleware: MiddlewareSettings = MiddlewareSettings()
    auth: AuthSettings = AuthSettings()
    media: MediaSettings = MediaSettings()
    cache: CacheSettings = CacheSettings()
    jobs: JobsSettings = JobsSettings()
    redis: RedisSettings = RedisSettings()
    docs: DocsSettings = DocsSettings()
    db: DbSettings = DbSettings()
    security: SecuritySettings = SecuritySettings()
    notifications: NotificationSettings = NotificationSettings()
    maintenance: MaintenanceSettings = MaintenanceSettings()


settings = Settings()
