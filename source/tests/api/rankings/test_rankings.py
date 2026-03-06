from fastapi import status

from source.config.settings import settings


async def test_current_rankings_use_database_data(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/rankings/current")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"][0]["player_name"] == "Novak Djokovic"
    assert payload["data"][0]["ranking_type"] == "atp"


async def test_rankings_history_returns_snapshots(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/rankings/atp/history")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]
    assert payload["data"][0]["entries"]


async def test_current_wta_rankings_are_available(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/rankings/current?ranking_type=wta")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]
    assert payload["data"][0]["ranking_type"] == "wta"
