from fastapi import APIRouter, Query, Request

from source.schemas.pydantic.auth import MessageResponse
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.match import MatchDetail, MatchEventCreateRequest, MatchEventItem, MatchScoreUpdateRequest, MatchStatsUpdateRequest, MatchStatusUpdateRequest, MatchSummary
from source.services import AdminContentService

router = APIRouter(prefix="/matches", tags=["admin-matches"])
service = AdminContentService()


@router.get("", response_model=SuccessResponse[list[MatchSummary]])
async def list_admin_matches(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    tournament_id: int | None = Query(default=None),
    player_id: int | None = Query(default=None),
    round_code: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
) -> SuccessResponse[list[MatchSummary]]:
    return await service.list_admin_matches(
        search=search,
        status=status,
        tournament_id=tournament_id,
        player_id=player_id,
        round_code=round_code,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("", response_model=SuccessResponse[MatchDetail])
async def create_admin_match(request: Request, payload: dict) -> SuccessResponse[MatchDetail]:
    return await service.create_admin_match(payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.get("/{match_id}", response_model=SuccessResponse[MatchDetail])
async def get_admin_match(match_id: int) -> SuccessResponse[MatchDetail]:
    return await service.get_admin_match(match_id)


@router.patch("/{match_id}", response_model=SuccessResponse[MatchDetail])
async def patch_admin_match(request: Request, match_id: int, payload: dict) -> SuccessResponse[MatchDetail]:
    return await service.update_admin_match(match_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.delete("/{match_id}", response_model=MessageResponse)
async def delete_admin_match(request: Request, match_id: int) -> MessageResponse:
    return await service.delete_admin_match(match_id, actor_id=getattr(request.state.current_user, 'id', None))


@router.patch("/{match_id}/status", response_model=SuccessResponse[MatchDetail])
async def patch_admin_match_status(request: Request, match_id: int, payload: MatchStatusUpdateRequest) -> SuccessResponse[MatchDetail]:
    return await service.update_admin_match_status(match_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.patch("/{match_id}/score", response_model=SuccessResponse[MatchDetail])
async def patch_admin_match_score(request: Request, match_id: int, payload: MatchScoreUpdateRequest) -> SuccessResponse[MatchDetail]:
    return await service.update_admin_match_score(match_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.patch("/{match_id}/stats", response_model=SuccessResponse[MatchDetail])
async def patch_admin_match_stats(request: Request, match_id: int, payload: MatchStatsUpdateRequest) -> SuccessResponse[MatchDetail]:
    return await service.update_admin_match_stats(match_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{match_id}/events", response_model=SuccessResponse[MatchEventItem])
async def create_admin_match_event(request: Request, match_id: int, payload: MatchEventCreateRequest) -> SuccessResponse[MatchEventItem]:
    return await service.create_admin_match_event(match_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{match_id}/finalize", response_model=MessageResponse)
async def finalize_admin_match(request: Request, match_id: int) -> MessageResponse:
    return await service.finalize_admin_match(match_id, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{match_id}/reopen", response_model=MessageResponse)
async def reopen_admin_match(request: Request, match_id: int) -> MessageResponse:
    return await service.reopen_admin_match(match_id, actor_id=getattr(request.state.current_user, 'id', None))
