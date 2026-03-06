from fastapi.testclient import TestClient

from source.config.settings import settings
from source.main import create_app


def test_security_headers_present(prepared_test_db: str) -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get('/api/v1/health')
        assert response.status_code == 200
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['x-frame-options'] == 'DENY'
        assert 'content-security-policy' in response.headers


def test_api_rate_limit_returns_429(monkeypatch, prepared_test_db: str) -> None:
    monkeypatch.setattr(settings.security, 'api_rate_limit_requests', 1)
    monkeypatch.setattr(settings.security, 'api_rate_limit_window_seconds', 60)
    app = create_app()
    with TestClient(app) as client:
        first = client.get('/api/v1/players')
        second = client.get('/api/v1/players')
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json()['errors'][0]['code'] == 'RATE_LIMITED'


async def test_invalid_bearer_token_returns_401(async_client) -> None:
    response = await async_client.get('/api/v1/users/me', headers={'Authorization': 'Bearer invalid.token.value'})
    assert response.status_code == 401


async def test_sql_injection_like_queries_do_not_break_search(async_client) -> None:
    payloads = [
        "' OR 1=1 --",
        "\"; DROP TABLE players; --",
        "novak' UNION SELECT * FROM users --",
    ]
    for query in payloads:
        response = await async_client.get('/api/v1/search', params={'q': query})
        assert response.status_code == 200

    players_response = await async_client.get('/api/v1/players')
    assert players_response.status_code == 200

async def test_private_integration_endpoint_is_rejected(async_client, admin_auth_headers) -> None:
    response = await async_client.patch(
        '/api/v1/admin/integrations/live-provider',
        headers=admin_auth_headers,
        json={'endpoint': 'http://192.168.1.15/feed'},
    )
    assert response.status_code == 422

