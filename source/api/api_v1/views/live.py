from fastapi import APIRouter, WebSocket

from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.match import MatchDetail, MatchEventItem, MatchSummary
from source.services import PublicDataService

router = APIRouter(prefix="/live", tags=["live"])
service = PublicDataService()


@router.get("", response_model=SuccessResponse[list[MatchSummary]])
async def get_live_matches() -> SuccessResponse[list[MatchSummary]]:
    return await service.list_live_matches()


@router.get("/feed", response_model=SuccessResponse[list[MatchEventItem]])
async def get_live_feed() -> SuccessResponse[list[MatchEventItem]]:
    return await service.get_live_feed()


@router.get("/{match_id}", response_model=SuccessResponse[MatchDetail])
async def get_live_match(match_id: int) -> SuccessResponse[MatchDetail]:
    return await service.get_live_match(match_id)


@router.websocket("/ws/live")
async def live_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"event": "connected", "channels": []})
    await websocket.close()
