from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorItem(BaseModel):
    code: str
    message: str
    field: str | None = None


class PaginationMeta(BaseModel):
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0

    @classmethod
    def build(cls, page: int, per_page: int, total: int) -> "PaginationMeta":
        safe_per_page = max(per_page, 1)
        return cls(
            page=page,
            per_page=safe_per_page,
            total=total,
            total_pages=ceil(total / safe_per_page) if total else 0,
        )


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    meta: dict = Field(default_factory=dict)
    errors: None = None


class ErrorResponse(BaseModel):
    success: bool = False
    data: None = None
    meta: dict = Field(default_factory=dict)
    errors: list[ErrorItem]


class PaginatedResponse(SuccessResponse[list[T]], Generic[T]):
    meta: PaginationMeta
