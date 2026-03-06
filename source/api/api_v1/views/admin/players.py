from fastapi import APIRouter, Request

from source.schemas.pydantic.auth import MessageResponse
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.player import PlayerDetail, PlayerSummary
from source.services import AdminContentService

router = APIRouter(prefix="/players", tags=["admin-players"])
service = AdminContentService()


@router.get("", response_model=SuccessResponse[list[PlayerSummary]])
async def list_admin_players(search: str | None = None, country_code: str | None = None, hand: str | None = None, status: str | None = None) -> SuccessResponse[list[PlayerSummary]]:
    return await service.list_admin_players(search=search, country_code=country_code, hand=hand, status=status)


@router.post("", response_model=SuccessResponse[PlayerDetail])
async def create_admin_player(request: Request, payload: dict) -> SuccessResponse[PlayerDetail]:
    return await service.create_admin_player(payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.get("/{player_id}", response_model=SuccessResponse[PlayerDetail])
async def get_admin_player(player_id: int) -> SuccessResponse[PlayerDetail]:
    return await service.get_admin_player(player_id)


@router.patch("/{player_id}", response_model=SuccessResponse[PlayerDetail])
async def patch_admin_player(request: Request, player_id: int, payload: dict) -> SuccessResponse[PlayerDetail]:
    return await service.update_admin_player(player_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.delete("/{player_id}", response_model=MessageResponse)
async def delete_admin_player(request: Request, player_id: int) -> MessageResponse:
    return await service.delete_admin_player(player_id, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/import", response_model=MessageResponse)
async def import_admin_players(request: Request, payload: dict | None = None) -> MessageResponse:
    return await service.import_admin_players(payload or {}, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{player_id}/photo", response_model=MessageResponse)
async def upload_admin_player_photo(request: Request, player_id: int, payload: dict | None = None) -> MessageResponse:
    return await service.upload_admin_player_photo(player_id, payload or {}, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{player_id}/recalculate-stats", response_model=MessageResponse)
async def recalculate_admin_player_stats(request: Request, player_id: int) -> MessageResponse:
    return await service.recalculate_admin_player_stats(player_id, actor_id=getattr(request.state.current_user, 'id', None))
