from fastapi import APIRouter, Query, Request

from source.schemas.pydantic.admin import AdminActionResult
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.news import NewsArticleCreateRequest, NewsArticleDetail, NewsArticleSummary, NewsCategoryItem, NewsStatusRequest, TagItem
from source.services import AdminContentService, PortalQueryService

router = APIRouter(prefix="/news", tags=["admin-news"])
service = AdminContentService()
query_service = PortalQueryService()


@router.get("", response_model=SuccessResponse[list[NewsArticleSummary]])
async def list_admin_news(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> SuccessResponse[list[NewsArticleSummary]]:
    return await service.list_admin_news(search=search, status=status)


@router.post("", response_model=SuccessResponse[NewsArticleDetail])
async def create_admin_news(request: Request, payload: NewsArticleCreateRequest) -> SuccessResponse[NewsArticleDetail]:
    return await service.create_admin_news(payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.get("/{news_id}", response_model=SuccessResponse[NewsArticleDetail])
async def get_admin_news(news_id: int) -> SuccessResponse[NewsArticleDetail]:
    return await service.get_admin_news(news_id)


@router.patch("/{news_id}", response_model=SuccessResponse[NewsArticleDetail])
async def patch_admin_news(request: Request, news_id: int, payload: NewsArticleCreateRequest) -> SuccessResponse[NewsArticleDetail]:
    return await service.update_admin_news(news_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.delete("/{news_id}", response_model=SuccessResponse[AdminActionResult])
async def delete_admin_news(request: Request, news_id: int) -> SuccessResponse[AdminActionResult]:
    return await service.delete_admin_news(news_id, actor_id=getattr(request.state.current_user, 'id', None))


@router.patch("/{news_id}/status", response_model=SuccessResponse[NewsArticleDetail])
async def patch_admin_news_status(request: Request, news_id: int, payload: NewsStatusRequest) -> SuccessResponse[NewsArticleDetail]:
    return await service.update_admin_news_status(news_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{news_id}/publish", response_model=SuccessResponse[AdminActionResult])
async def publish_admin_news(request: Request, news_id: int) -> SuccessResponse[AdminActionResult]:
    return await service.publish_admin_news(news_id, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{news_id}/schedule", response_model=SuccessResponse[AdminActionResult])
async def schedule_admin_news(request: Request, news_id: int, payload: NewsStatusRequest) -> SuccessResponse[AdminActionResult]:
    return await service.schedule_admin_news(news_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{news_id}/cover", response_model=SuccessResponse[AdminActionResult])
async def upload_admin_news_cover(request: Request, news_id: int, payload: dict | None = None) -> SuccessResponse[AdminActionResult]:
    return await service.upload_admin_news_cover(news_id, payload or {}, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{news_id}/tags", response_model=SuccessResponse[list[TagItem]])
async def attach_admin_news_tags(request: Request, news_id: int, payload: dict | None = None) -> SuccessResponse[list[TagItem]]:
    return await service.attach_admin_news_tags(news_id, payload or {}, actor_id=getattr(request.state.current_user, 'id', None))


@router.get("/categories/list", response_model=SuccessResponse[list[NewsCategoryItem]])
async def list_admin_categories() -> SuccessResponse[list[NewsCategoryItem]]:
    return await query_service.get_news_categories()


@router.get("/tags/list", response_model=SuccessResponse[list[TagItem]])
async def list_admin_tags() -> SuccessResponse[list[TagItem]]:
    return await query_service.get_news_tags()
