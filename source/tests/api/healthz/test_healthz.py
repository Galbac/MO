from fastapi import status

from source.config.settings import settings


async def test_healthz_returns_ok(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
