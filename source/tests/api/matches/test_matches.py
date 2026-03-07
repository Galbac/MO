from fastapi import status

from source.config.settings import settings


async def test_match_detail_returns_score_and_stats(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/matches/1")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["score"]["sets"]
    assert payload["data"]["stats"]["duration_minutes"] == 196


async def test_match_prediction_and_momentum_endpoints(async_client) -> None:
    prediction_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/matches/1/prediction")
    assert prediction_response.status_code == status.HTTP_200_OK
    prediction = prediction_response.json()["data"]
    assert prediction["player1_probability"] > 0
    assert prediction["player2_probability"] > 0

    momentum_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/matches/2/momentum")
    assert momentum_response.status_code == status.HTTP_200_OK
    momentum = momentum_response.json()["data"]
    assert "recent_points" in momentum
