from fastapi import APIRouter

from source.services import PortalQueryService
from source.schemas.pydantic.common import PaginatedResponse, SuccessResponse
from source.schemas.pydantic.news import NewsArticleDetail, NewsArticleSummary, NewsCategoryItem, TagItem

router = APIRouter(prefix="/news", tags=["news"])
service = PortalQueryService()


@router.get("", response_model=PaginatedResponse[NewsArticleSummary])
async def get_news(page: int = 1, per_page: int = 20) -> PaginatedResponse[NewsArticleSummary]:
    return await service.list_news(page, per_page)


@router.get("/categories", response_model=SuccessResponse[list[NewsCategoryItem]])
async def get_news_categories() -> SuccessResponse[list[NewsCategoryItem]]:
    return await service.get_news_categories()


@router.get("/tags", response_model=SuccessResponse[list[TagItem]])
async def get_news_tags() -> SuccessResponse[list[TagItem]]:
    return await service.get_news_tags()


@router.get("/featured", response_model=SuccessResponse[list[NewsArticleSummary]])
async def get_featured_news() -> SuccessResponse[list[NewsArticleSummary]]:
    return await service.get_featured_news()


@router.get("/related", response_model=SuccessResponse[list[NewsArticleSummary]])
async def get_related_news(slug: str | None = None) -> SuccessResponse[list[NewsArticleSummary]]:
    return await service.get_related_news(slug)


@router.get("/{slug}", response_model=SuccessResponse[NewsArticleDetail])
async def get_news_article(slug: str) -> SuccessResponse[NewsArticleDetail]:
    return await service.get_news_article(slug)
