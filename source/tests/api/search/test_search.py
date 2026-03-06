from fastapi import status

from source.config.settings import settings


async def test_search_returns_db_backed_entities(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/search", params={"q": "Djokovic"})

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]["players"]
    assert payload["data"]["players"][0]["slug"] == "novak-djokovic"


async def test_search_suggestions_are_generated_from_results(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/search/suggestions", params={"q": "Australian"})

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]
