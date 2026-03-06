from fastapi import APIRouter, status

from source.schemas.pydantic.auth import MessageResponse
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.media import MediaFile
from source.services import OperationsService

router = APIRouter(prefix="/media", tags=["admin-media"])
service = OperationsService()


@router.get("", response_model=SuccessResponse[list[MediaFile]])
async def get_admin_media() -> SuccessResponse[list[MediaFile]]:
    return await service.list_media()


@router.post("/upload", response_model=SuccessResponse[MediaFile], status_code=status.HTTP_201_CREATED)
async def post_admin_media_upload(payload: dict) -> SuccessResponse[MediaFile]:
    return await service.create_media_record(payload)


@router.delete("/{media_id}", response_model=MessageResponse)
async def delete_admin_media(media_id: int) -> MessageResponse:
    return await service.delete_media(media_id)
