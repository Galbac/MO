from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str | None = None
    environment: str | None = None
    checked_at: datetime | None = None
    version: str | None = None


class ReadinessDependency(BaseModel):
    status: str
    backend: str | None = None
    detail: str | None = None
    checked_at: datetime | None = None


class ReadinessResponse(BaseModel):
    status: str
    checked_at: datetime | None = None
    dependencies: dict[str, ReadinessDependency] = Field(default_factory=dict)
