from fastapi import status

from source.config.settings import settings


async def test_players_list_returns_success_envelope(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/players")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["data"], list)
    assert payload["errors"] is None


async def test_players_endpoint_uses_seeded_database_data(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/players")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"][0]["slug"] == "novak-djokovic"
