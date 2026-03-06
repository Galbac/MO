from fastapi import APIRouter, Query

from source.services import PortalQueryService
from source.schemas.pydantic.common import PaginatedResponse, SuccessResponse
from source.schemas.pydantic.match import MatchSummary
from source.schemas.pydantic.player import (
    H2HResponse,
    PlayerComparison,
    PlayerDetail,
    PlayerNewsItem,
    PlayerStats,
    PlayerSummary,
    RankingHistoryPoint,
    TitleItem,
    UpcomingMatchItem,
)

router = APIRouter(prefix="/players", tags=["players"])
service = PortalQueryService()


@router.get("", response_model=PaginatedResponse[PlayerSummary])
async def get_players(
    search: str | None = None,
    country_code: str | None = None,
    hand: str | None = None,
    status: str | None = None,
    rank_from: int | None = None,
    rank_to: int | None = None,
    page: int = 1,
    per_page: int = 20,
) -> PaginatedResponse[PlayerSummary]:
    return await service.list_players(search, country_code, hand, status, rank_from, rank_to, page, per_page)


@router.get("/compare", response_model=SuccessResponse[PlayerComparison])
async def compare_players(
    player1_id: int = Query(...),
    player2_id: int = Query(...),
) -> SuccessResponse[PlayerComparison]:
    return await service.compare_players(player1_id, player2_id)


@router.get("/h2h", response_model=SuccessResponse[H2HResponse])
async def get_h2h(player1_id: int = Query(...), player2_id: int = Query(...)) -> SuccessResponse[H2HResponse]:
    return await service.get_h2h(player1_id, player2_id)


@router.get("/{player_id}", response_model=SuccessResponse[PlayerDetail])
async def get_player(player_id: int) -> SuccessResponse[PlayerDetail]:
    return await service.get_player(player_id)


@router.get("/{player_id}/stats", response_model=SuccessResponse[PlayerStats])
async def get_player_stats(player_id: int) -> SuccessResponse[PlayerStats]:
    return await service.get_player_stats(player_id)


@router.get("/{player_id}/matches", response_model=PaginatedResponse[MatchSummary])
async def get_player_matches(player_id: int, page: int = 1, per_page: int = 20) -> PaginatedResponse[MatchSummary]:
    return await service.get_player_matches(player_id, page, per_page)


@router.get("/{player_id}/ranking-history", response_model=SuccessResponse[list[RankingHistoryPoint]])
async def get_player_ranking_history(player_id: int) -> SuccessResponse[list[RankingHistoryPoint]]:
    return await service.get_player_ranking_history(player_id)


@router.get("/{player_id}/titles", response_model=SuccessResponse[list[TitleItem]])
async def get_player_titles(player_id: int) -> SuccessResponse[list[TitleItem]]:
    return await service.get_player_titles(player_id)


@router.get("/{player_id}/news", response_model=SuccessResponse[list[PlayerNewsItem]])
async def get_player_news(player_id: int) -> SuccessResponse[list[PlayerNewsItem]]:
    return await service.get_player_news(player_id)


@router.get("/{player_id}/upcoming-matches", response_model=SuccessResponse[list[UpcomingMatchItem]])
async def get_player_upcoming_matches(player_id: int) -> SuccessResponse[list[UpcomingMatchItem]]:
    return await service.get_player_upcoming_matches(player_id)
