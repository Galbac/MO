from fastapi import APIRouter

from source.services import PortalQueryService
from source.schemas.pydantic.common import PaginatedResponse, SuccessResponse
from source.schemas.pydantic.match import MatchSummary
from source.schemas.pydantic.news import NewsArticleSummary
from source.schemas.pydantic.player import PlayerSummary
from source.schemas.pydantic.tournament import ChampionItem, DrawMatchItem, TournamentDetail, TournamentSummary

router = APIRouter(prefix="/tournaments", tags=["tournaments"])
service = PortalQueryService()


@router.get("", response_model=PaginatedResponse[TournamentSummary])
async def get_tournaments(page: int = 1, per_page: int = 20) -> PaginatedResponse[TournamentSummary]:
    return await service.list_tournaments(page, per_page)


@router.get("/{tournament_id}", response_model=SuccessResponse[TournamentDetail])
async def get_tournament(tournament_id: int) -> SuccessResponse[TournamentDetail]:
    return await service.get_tournament(tournament_id)


@router.get("/{tournament_id}/matches", response_model=SuccessResponse[list[MatchSummary]])
async def get_tournament_matches(tournament_id: int) -> SuccessResponse[list[MatchSummary]]:
    return await service.get_tournament_matches(tournament_id)


@router.get("/{tournament_id}/draw", response_model=SuccessResponse[list[DrawMatchItem]])
async def get_tournament_draw(tournament_id: int) -> SuccessResponse[list[DrawMatchItem]]:
    return await service.get_tournament_draw(tournament_id)


@router.get("/{tournament_id}/players", response_model=SuccessResponse[list[PlayerSummary]])
async def get_tournament_players(tournament_id: int) -> SuccessResponse[list[PlayerSummary]]:
    return await service.get_tournament_players(tournament_id)


@router.get("/{tournament_id}/champions", response_model=SuccessResponse[list[ChampionItem]])
async def get_tournament_champions(tournament_id: int) -> SuccessResponse[list[ChampionItem]]:
    return await service.get_tournament_champions(tournament_id)


@router.get("/{tournament_id}/news", response_model=SuccessResponse[list[NewsArticleSummary]])
async def get_tournament_news(tournament_id: int) -> SuccessResponse[list[NewsArticleSummary]]:
    return await service.get_tournament_news(tournament_id)


@router.get("/calendar", response_model=SuccessResponse[list[TournamentSummary]])
async def get_tournament_calendar() -> SuccessResponse[list[TournamentSummary]]:
    return await service.get_tournament_calendar()
