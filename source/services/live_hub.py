from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi import WebSocket


class LiveHub:
    def __init__(self) -> None:
        self._connections: dict[int, tuple[WebSocket, set[str]]] = {}

    async def connect(self, websocket: WebSocket) -> int:
        await websocket.accept()
        connection_id = id(websocket)
        self._connections[connection_id] = (websocket, set())
        return connection_id

    def disconnect(self, connection_id: int) -> None:
        self._connections.pop(connection_id, None)

    def subscribe(self, connection_id: int, channels: Iterable[str]) -> list[str]:
        websocket, current = self._connections[connection_id]
        del websocket
        for channel in channels:
            value = str(channel).strip()
            if value:
                current.add(value)
        return sorted(current)

    def unsubscribe(self, connection_id: int, channels: Iterable[str]) -> list[str]:
        websocket, current = self._connections[connection_id]
        del websocket
        for channel in channels:
            current.discard(str(channel).strip())
        return sorted(current)

    def channels(self, connection_id: int) -> list[str]:
        websocket, current = self._connections[connection_id]
        del websocket
        return sorted(current)

    async def broadcast(self, *, channels: Iterable[str], payload: dict[str, Any]) -> None:
        target_channels = {str(channel).strip() for channel in channels if str(channel).strip()}
        stale: list[int] = []
        for connection_id, (websocket, subscribed) in self._connections.items():
            if not subscribed.intersection(target_channels):
                continue
            try:
                await websocket.send_json(payload)
            except Exception:  # noqa: BLE001
                stale.append(connection_id)
        for connection_id in stale:
            self.disconnect(connection_id)


live_hub = LiveHub()
