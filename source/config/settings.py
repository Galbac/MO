import os

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_postgres_url() -> str:
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    database = os.getenv('POSTGRES_DB', 'tennis_portal')
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', 'postgres')
    return f'postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}'


def _default_site_domain() -> str:
    return os.getenv('FASTAPI_CFG__SITE__DOMAIN', 'makhachkalaopen.ru')


def _default_site_scheme() -> str:
    return os.getenv('FASTAPI_CFG__SITE__SCHEME', 'https')


def _default_site_base_url() -> str:
    value = os.getenv('FASTAPI_CFG__SITE__BASE_URL', '').strip().rstrip('/')
    if value:
        return value
    return f'{_default_site_scheme()}://{_default_site_domain()}'


def _default_cors_origins() -> list[str]:
    raw = os.getenv('FASTAPI_CFG__MIDDLEWARE__CORS_ORIGINS', '').strip()
    if raw:
        return [item.strip() for item in raw.split(',') if item.strip()]
    base_url = _default_site_base_url()
    return [
        base_url,
        'http://localhost',
        'http://127.0.0.1',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]


def _default_domain_email(local_part: str) -> str:
    return f'{local_part}@{_default_site_domain()}'



class RunConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    production: bool = False
    dev_reload: bool = False


class ProjectName(BaseModel):
    title: str = "Makhachkala Open"
    path: str = ""
    slug: str = "makhachkala_open"


class ApiV1Prefix(BaseModel):
    prefix: str = "/v1"


class ApiPrefix(BaseModel):
    prefix: str = "/api"
    v1: ApiV1Prefix = ApiV1Prefix()


class SiteSettings(BaseModel):
    domain: str = Field(default_factory=_default_site_domain)
    scheme: str = Field(default_factory=_default_site_scheme)
    base_url: str = Field(default_factory=_default_site_base_url)
    editorial_name: str = "Редакция Makhachkala Open"
    tagline: str = "Премиальный теннисный портал"
    admin_title: str = "Центр управления Makhachkala Open"


class ContactSettings(BaseModel):
    support_email: str = Field(default_factory=lambda: _default_domain_email('support'))
    noreply_email: str = Field(default_factory=lambda: _default_domain_email('noreply'))


class DemoAccountsSettings(BaseModel):
    admin_email: str = Field(default_factory=lambda: _default_domain_email('admin'))
    user_email: str = Field(default_factory=lambda: _default_domain_email('user'))
    editor_email: str = Field(default_factory=lambda: _default_domain_email('editor'))
    operator_email: str = Field(default_factory=lambda: _default_domain_email('operator'))
    admin_password: str = "AdminPass123"
    user_password: str = "UserPass123"
    editor_password: str = "EditorPass123"
    operator_password: str = "OperatorPass123"


class MiddlewareSettings(BaseModel):
    cors_origins: list[str] = Field(default_factory=_default_cors_origins)
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


class LoggingSettings(BaseModel):
    dir: str = "var/logs"
    access_enabled: bool = True



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
    site: SiteSettings = SiteSettings()
    contacts: ContactSettings = ContactSettings()
    demo: DemoAccountsSettings = DemoAccountsSettings()
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
    logging: LoggingSettings = LoggingSettings()


settings = Settings()
