from fastapi import status

from source.config.settings import settings


async def test_live_list_returns_live_matches(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/live")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]
    assert any(item["status"] == "live" for item in payload["data"])


async def test_live_feed_returns_events(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/live/feed")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]
    assert payload["data"][0]["event_type"]
