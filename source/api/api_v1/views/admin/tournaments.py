from fastapi import APIRouter, Request

from source.schemas.pydantic.auth import MessageResponse
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.tournament import TournamentDetail, TournamentSummary
from source.services import AdminContentService

router = APIRouter(prefix="/tournaments", tags=["admin-tournaments"])
service = AdminContentService()


@router.get("", response_model=SuccessResponse[list[TournamentSummary]])
async def list_admin_tournaments() -> SuccessResponse[list[TournamentSummary]]:
    return await service.list_admin_tournaments()


@router.post("", response_model=SuccessResponse[TournamentDetail])
async def create_admin_tournament(request: Request, payload: dict) -> SuccessResponse[TournamentDetail]:
    return await service.create_admin_tournament(payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.get("/{tournament_id}", response_model=SuccessResponse[TournamentDetail])
async def get_admin_tournament(tournament_id: int) -> SuccessResponse[TournamentDetail]:
    return await service.get_admin_tournament(tournament_id)


@router.patch("/{tournament_id}", response_model=SuccessResponse[TournamentDetail])
async def patch_admin_tournament(request: Request, tournament_id: int, payload: dict) -> SuccessResponse[TournamentDetail]:
    return await service.update_admin_tournament(tournament_id, payload, actor_id=getattr(request.state.current_user, 'id', None))


@router.delete("/{tournament_id}", response_model=MessageResponse)
async def delete_admin_tournament(request: Request, tournament_id: int) -> MessageResponse:
    return await service.delete_admin_tournament(tournament_id, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{tournament_id}/draw/generate", response_model=MessageResponse)
async def generate_admin_tournament_draw(request: Request, tournament_id: int) -> MessageResponse:
    return await service.generate_admin_tournament_draw(tournament_id, actor_id=getattr(request.state.current_user, 'id', None))


@router.post("/{tournament_id}/publish", response_model=MessageResponse)
async def publish_admin_tournament(request: Request, tournament_id: int) -> MessageResponse:
    return await service.publish_admin_tournament(tournament_id, actor_id=getattr(request.state.current_user, 'id', None))
