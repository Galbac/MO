from datetime import datetime

from fastapi import APIRouter, Query

from source.schemas.pydantic.admin import AdminSystemLogItem
from source.schemas.pydantic.common import SuccessResponse
from source.services.log_service import LogService

router = APIRouter(prefix="/logs", tags=["admin-logs"])
service = LogService()


@router.get("", response_model=SuccessResponse[list[AdminSystemLogItem]])
async def get_admin_logs(
    category: str = Query(default="application"),
    level: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> SuccessResponse[list[AdminSystemLogItem]]:
    rows = service.read(category, level=level, limit=limit)
    return SuccessResponse(data=[AdminSystemLogItem(timestamp=datetime.fromisoformat(item['timestamp']), category=str(item.get('category') or category), level=str(item.get('level') or 'info'), message=str(item.get('message') or ''), context=item.get('context') or {}) for item in rows])
