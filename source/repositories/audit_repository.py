from __future__ import annotations

from datetime import date, datetime

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

    async def list(self, session: AsyncSession) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        return list((await session.scalars(stmt)).all())

    async def get(self, session: AsyncSession, log_id: int) -> AuditLog | None:
        return await session.get(AuditLog, log_id)
