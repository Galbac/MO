from fastapi import status

from source.config.settings import settings


async def test_healthz_returns_ok(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


async def test_readiness_returns_dependency_status(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/health/ready")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload['status'] in {'ok', 'degraded'}
    assert payload['dependencies']['database']['status'] == 'ok'
    assert payload['dependencies']['runtime_state']['status'] == 'ok'
    assert payload['dependencies']['runtime_state']['backend'] in {'local', 'redis'}
