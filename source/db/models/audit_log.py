from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from source.db.models.base import Base
from source.db.models.mixins import IdIntPkMixin, TimestampMixin


class AuditLog(Base, IdIntPkMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    user_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
