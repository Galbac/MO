from fastapi import APIRouter, Query

from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.search import SearchResults, SearchSuggestion
from source.services import PublicDataService

router = APIRouter(prefix="/search", tags=["search"])
service = PublicDataService()


@router.get("", response_model=SuccessResponse[SearchResults])
async def search(q: str = Query(..., min_length=1, max_length=120), types: list[str] | None = Query(default=None)) -> SuccessResponse[SearchResults]:
    return await service.search(q, types=types)


@router.get("/suggestions", response_model=SuccessResponse[list[SearchSuggestion]])
async def search_suggestions(q: str = Query(..., min_length=1, max_length=120), types: list[str] | None = Query(default=None)) -> SuccessResponse[list[SearchSuggestion]]:
    return await service.search_suggestions(q, types=types)
