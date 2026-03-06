from fastapi import APIRouter, Query, status

from source.schemas.pydantic.admin import AdminActionResult, AdminMediaItem, AdminMediaSummary
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.media import MediaFile
from source.services import OperationsService

router = APIRouter(prefix="/media", tags=["admin-media"])
service = OperationsService()


@router.get("", response_model=SuccessResponse[list[AdminMediaItem]])
async def get_admin_media(
    content_type: str | None = Query(default=None),
    exists: bool | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> SuccessResponse[list[AdminMediaItem]]:
    return await service.list_admin_media(content_type=content_type, exists=exists, limit=limit)


@router.get("/summary", response_model=SuccessResponse[AdminMediaSummary])
async def get_admin_media_summary() -> SuccessResponse[AdminMediaSummary]:
    return await service.summarize_media()


@router.post("/upload", response_model=SuccessResponse[MediaFile], status_code=status.HTTP_201_CREATED)
async def post_admin_media_upload(payload: dict) -> SuccessResponse[MediaFile]:
    return await service.create_media_record(payload)


@router.get("/{media_id}", response_model=SuccessResponse[AdminMediaItem])
async def get_admin_media_item(media_id: int) -> SuccessResponse[AdminMediaItem]:
    return await service.get_admin_media(media_id)


@router.delete("/{media_id}", response_model=SuccessResponse[AdminActionResult])
async def delete_admin_media(media_id: int) -> SuccessResponse[AdminActionResult]:
    return await service.delete_media(media_id)
