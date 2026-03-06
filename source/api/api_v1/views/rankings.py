from fastapi import APIRouter

from source.schemas.pydantic.common import PaginatedResponse, SuccessResponse
from source.schemas.pydantic.ranking import PlayerRankingRecord, RankingEntry, RankingSnapshotItem
from source.services import PublicDataService

router = APIRouter(prefix="/rankings", tags=["rankings"])
service = PublicDataService()


@router.get("", response_model=PaginatedResponse[RankingEntry])
async def get_rankings(page: int = 1, per_page: int = 100, ranking_type: str | None = None, date: str | None = None) -> PaginatedResponse[RankingEntry]:
    return await service.get_rankings(page=page, per_page=per_page, ranking_type=ranking_type, ranking_date=date)


@router.get("/current", response_model=SuccessResponse[list[RankingEntry]])
async def get_current_rankings(ranking_type: str = 'atp') -> SuccessResponse[list[RankingEntry]]:
    return await service.get_current_rankings(ranking_type)


@router.get("/{ranking_type}/history", response_model=SuccessResponse[list[RankingSnapshotItem]])
async def get_rankings_history(ranking_type: str) -> SuccessResponse[list[RankingSnapshotItem]]:
    return await service.get_rankings_history(ranking_type)


@router.get("/player/{player_id}", response_model=SuccessResponse[list[PlayerRankingRecord]])
async def get_player_rankings(player_id: int) -> SuccessResponse[list[PlayerRankingRecord]]:
    return await service.get_player_rankings(player_id)


@router.get("/race", response_model=SuccessResponse[list[RankingEntry]])
async def get_race_rankings() -> SuccessResponse[list[RankingEntry]]:
    return await service.get_race_rankings()
