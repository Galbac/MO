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
    slugs = {item["slug"] for item in payload["data"]}
    assert {"novak-djokovic", "iga-swiatek"}.issubset(slugs)


async def test_player_detail_uses_rebuilt_aggregate_stats(async_client, admin_auth_headers) -> None:
    finalize = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/finalize",
        headers=admin_auth_headers,
    )
    assert finalize.status_code == status.HTTP_200_OK

    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/players/3")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["stats"]["wins"] == 1
    assert payload["stats"]["losses"] == 0
    assert payload["stats"]["hard_record"] == "1-0"
    assert payload["form"][:1] == ["W"]
