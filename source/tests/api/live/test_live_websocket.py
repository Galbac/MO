import asyncio
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from source.main import create_app
from source.services import live_hub


def test_live_websocket_supports_subscribe_and_manual_broadcast(prepared_test_db: str) -> None:
    app = create_app()
    with TestClient(app) as client:
        with client.websocket_connect('/api/v1/live/ws/live') as websocket:
            connected = websocket.receive_json()
            assert connected['event'] == 'connected'

            websocket.send_json({'action': 'subscribe', 'channels': ['live:match:2']})
            subscribed = websocket.receive_json()
            assert subscribed['event'] == 'subscribed'
            assert 'live:match:2' in subscribed['channels']

            asyncio.run(live_hub.broadcast(channels=['live:match:2'], payload={'event': 'score_updated', 'match_id': 2, 'data': {'score_summary': '6-4 4-6 4-2'}}))
            payload = websocket.receive_json()
            assert payload['event'] == 'score_updated'
            assert payload['match_id'] == 2
            assert payload['data']['score_summary'] == '6-4 4-6 4-2'


async def test_score_update_triggers_live_broadcast(async_client, admin_auth_headers, monkeypatch) -> None:
    broadcast = AsyncMock()
    monkeypatch.setattr(live_hub, 'broadcast', broadcast)

    response = await async_client.patch(
        '/api/v1/admin/matches/2/score',
        headers=admin_auth_headers,
        json={'score_summary': '6-4 4-6 4-2', 'sets': []},
    )
    assert response.status_code == 200

    broadcast.assert_awaited()
    kwargs = broadcast.await_args.kwargs
    assert 'live:match:2' in kwargs['channels']
    assert kwargs['payload']['event'] == 'score_updated'
    assert kwargs['payload']['match_id'] == 2
