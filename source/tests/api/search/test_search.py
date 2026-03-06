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


async def test_search_matches_normalized_slug_variants(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/search", params={'q': 'djokovic sinner'})
    assert response.status_code == 200
    payload = response.json()['data']
    assert any(item['slug'] == 'djokovic-vs-sinner-ao-2026-final' for item in payload['matches'])


async def test_search_respects_types_filter(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/search", params={"q": "Djokovic", "types": ["players"]})
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["players"]
    assert payload["news"] == []
    assert payload["matches"] == []


async def test_search_rejects_invalid_type(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/search", params={"q": "Djokovic", "types": ["unknown"]})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_search_rejects_blank_query(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/search", params={"q": "   "})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
