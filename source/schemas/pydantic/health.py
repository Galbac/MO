from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class ReadinessDependency(BaseModel):
    status: str
    backend: str | None = None
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    dependencies: dict[str, ReadinessDependency] = Field(default_factory=dict)
