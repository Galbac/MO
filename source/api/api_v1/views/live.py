from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.match import MatchDetail, MatchEventItem, MatchSummary
from source.services import PublicDataService, live_hub

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
    connection_id = await live_hub.connect(websocket)
    try:
        initial_channels = [item for item in websocket.query_params.get('channels', '').split(',') if item]
        if initial_channels:
            subscribed = live_hub.subscribe(connection_id, initial_channels)
        else:
            subscribed = []
        await websocket.send_json({"event": "connected", "channels": subscribed})
        while True:
            message = await websocket.receive_json()
            action = str(message.get('action') or '').strip().lower()
            channels = message.get('channels') or []
            if isinstance(channels, str):
                channels = [item for item in channels.split(',') if item]
            if action == 'subscribe':
                subscribed = live_hub.subscribe(connection_id, channels)
                await websocket.send_json({"event": "subscribed", "channels": subscribed})
            elif action == 'unsubscribe':
                subscribed = live_hub.unsubscribe(connection_id, channels)
                await websocket.send_json({"event": "unsubscribed", "channels": subscribed})
            elif action == 'ping':
                await websocket.send_json({"event": "pong", "channels": live_hub.channels(connection_id)})
            else:
                await websocket.send_json({"event": "error", "message": "Unsupported action"})
    except WebSocketDisconnect:
        live_hub.disconnect(connection_id)
    except Exception:
        live_hub.disconnect(connection_id)
        raise
