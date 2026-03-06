from fastapi.testclient import TestClient

from source.config.settings import settings
from source.main import create_app


def test_security_headers_present() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get('/api/v1/health')
        assert response.status_code == 200
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['x-frame-options'] == 'DENY'
        assert 'content-security-policy' in response.headers


def test_api_rate_limit_returns_429(monkeypatch) -> None:
    monkeypatch.setattr(settings.security, 'api_rate_limit_requests', 1)
    monkeypatch.setattr(settings.security, 'api_rate_limit_window_seconds', 60)
    app = create_app()
    with TestClient(app) as client:
        first = client.get('/api/v1/players')
        second = client.get('/api/v1/players')
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json()['errors'][0]['code'] == 'RATE_LIMITED'
