from fastapi import status

from source.config.settings import settings


async def test_match_detail_returns_score_and_stats(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/matches/1")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["score"]["sets"]
    assert payload["data"]["stats"]["duration_minutes"] == 196
