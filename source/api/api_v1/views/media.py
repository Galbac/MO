from fastapi import APIRouter, Depends, UploadFile, status

from source.api.dependencies.auth import require_roles
from source.schemas.pydantic.common import ActionResult, SuccessResponse
from source.schemas.pydantic.media import MediaFile
from source.services import OperationsService

router = APIRouter(prefix="/media", tags=["media"])
service = OperationsService()


@router.post(
    "/upload",
    response_model=SuccessResponse[MediaFile],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin", "editor", "operator"))],
)
async def upload_media(file: UploadFile) -> SuccessResponse[MediaFile]:
    return await service.upload_media_file(file)


@router.get("/{media_id}", response_model=SuccessResponse[MediaFile])
async def get_media(media_id: int) -> SuccessResponse[MediaFile]:
    return await service.get_media(media_id)


@router.delete(
    "/{media_id}",
    response_model=SuccessResponse[ActionResult],
    dependencies=[Depends(require_roles("admin", "editor", "operator"))],
)
async def delete_media(media_id: int) -> SuccessResponse[ActionResult]:
    return await service.delete_media(media_id)
