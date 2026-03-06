from fastapi import APIRouter

from source.schemas.pydantic.admin import AdminActionResult
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.news import NewsCategoryItem, TagItem
from source.services import AdminSupportService

router = APIRouter(tags=["admin-taxonomy"])
service = AdminSupportService()


@router.get("/news-categories", response_model=SuccessResponse[list[NewsCategoryItem]])
async def get_admin_news_categories() -> SuccessResponse[list[NewsCategoryItem]]:
    return await service.list_categories()


@router.post("/news-categories", response_model=SuccessResponse[AdminActionResult])
async def create_admin_news_category(payload: dict) -> SuccessResponse[AdminActionResult]:
    return await service.create_category(payload)


@router.patch("/news-categories/{category_id}", response_model=SuccessResponse[AdminActionResult])
async def patch_admin_news_category(category_id: int, payload: dict) -> SuccessResponse[AdminActionResult]:
    return await service.update_category(category_id, payload)


@router.delete("/news-categories/{category_id}", response_model=SuccessResponse[AdminActionResult])
async def delete_admin_news_category(category_id: int) -> SuccessResponse[AdminActionResult]:
    return await service.delete_category(category_id)


@router.get("/tags", response_model=SuccessResponse[list[TagItem]])
async def get_admin_tags() -> SuccessResponse[list[TagItem]]:
    return await service.list_tags()


@router.post("/tags", response_model=SuccessResponse[AdminActionResult])
async def create_admin_tag(payload: dict) -> SuccessResponse[AdminActionResult]:
    return await service.create_tag(payload)


@router.patch("/tags/{tag_id}", response_model=SuccessResponse[AdminActionResult])
async def patch_admin_tag(tag_id: int, payload: dict) -> SuccessResponse[AdminActionResult]:
    return await service.update_tag(tag_id, payload)


@router.delete("/tags/{tag_id}", response_model=SuccessResponse[AdminActionResult])
async def delete_admin_tag(tag_id: int) -> SuccessResponse[AdminActionResult]:
    return await service.delete_tag(tag_id)
