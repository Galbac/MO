from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import AuditLog


def _json_ready(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value


def _parse_date_floor(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _parse_date_ceil(value: str) -> datetime:
    if 'T' in value:
        parsed = datetime.fromisoformat(value)
    else:
        parsed = datetime.combine(date.fromisoformat(value), time.max)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


class AuditRepository:
    async def create(self, session: AsyncSession, payload: dict) -> AuditLog:
        item = AuditLog(
            user_id=payload.get('user_id'),
            action=payload.get('action'),
            entity_type=payload.get('entity_type'),
            entity_id=payload.get('entity_id'),
            before_json=_json_ready(payload.get('before_json')),
            after_json=_json_ready(payload.get('after_json')),
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    async def list(
        self,
        session: AsyncSession,
        *,
        user_id: int | None = None,
        entity_type: str | None = None,
        action: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if date_from:
            stmt = stmt.where(AuditLog.created_at >= _parse_date_floor(date_from))
        if date_to:
            stmt = stmt.where(AuditLog.created_at <= _parse_date_ceil(date_to))
        stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        return list((await session.scalars(stmt)).all())

    async def get(self, session: AsyncSession, log_id: int) -> AuditLog | None:
        return await session.get(AuditLog, log_id)
