from fastapi import APIRouter

from source.services import PortalQueryService
from source.schemas.pydantic.common import PaginatedResponse, SuccessResponse
from source.schemas.pydantic.match import MatchDetail, MatchEventItem, MatchPreview, MatchScore, MatchStats, MatchSummary
from source.schemas.pydantic.player import H2HResponse

router = APIRouter(prefix="/matches", tags=["matches"])
service = PortalQueryService()


@router.get("", response_model=PaginatedResponse[MatchSummary])
async def get_matches(page: int = 1, per_page: int = 20, status: str | None = None) -> PaginatedResponse[MatchSummary]:
    return await service.list_matches(page, per_page, status)


@router.get("/upcoming", response_model=SuccessResponse[list[MatchSummary]])
async def get_upcoming_matches() -> SuccessResponse[list[MatchSummary]]:
    return await service.get_upcoming_matches()


@router.get("/results", response_model=SuccessResponse[list[MatchSummary]])
async def get_match_results() -> SuccessResponse[list[MatchSummary]]:
    return await service.get_match_results()


@router.get("/{match_id}", response_model=SuccessResponse[MatchDetail])
async def get_match(match_id: int) -> SuccessResponse[MatchDetail]:
    return await service.get_match(match_id)


@router.get("/{match_id}/score", response_model=SuccessResponse[MatchScore])
async def get_match_score(match_id: int) -> SuccessResponse[MatchScore]:
    return await service.get_match_score(match_id)


@router.get("/{match_id}/stats", response_model=SuccessResponse[MatchStats])
async def get_match_stats(match_id: int) -> SuccessResponse[MatchStats]:
    return await service.get_match_stats(match_id)


@router.get("/{match_id}/timeline", response_model=SuccessResponse[list[MatchEventItem]])
async def get_match_timeline(match_id: int) -> SuccessResponse[list[MatchEventItem]]:
    return await service.get_match_timeline(match_id)


@router.get("/{match_id}/h2h", response_model=SuccessResponse[H2HResponse])
async def get_match_h2h(match_id: int) -> SuccessResponse[H2HResponse]:
    return await service.get_match_h2h(match_id)


@router.get("/{match_id}/preview", response_model=SuccessResponse[MatchPreview])
async def get_match_preview(match_id: int) -> SuccessResponse[MatchPreview]:
    return await service.get_match_preview(match_id)


@router.get("/{match_id}/point-by-point", response_model=SuccessResponse[list[MatchEventItem]])
async def get_match_point_by_point(match_id: int) -> SuccessResponse[list[MatchEventItem]]:
    return await service.get_match_point_by_point(match_id)
