from fastapi import status

from source.config.settings import settings


async def test_user_profile_requires_auth(async_client) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_admin_endpoint_forbids_regular_user(async_client, user_auth_headers) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users", headers=user_auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_admin_endpoint_allows_admin(async_client, admin_auth_headers) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users", headers=admin_auth_headers)
    assert response.status_code == status.HTTP_200_OK


async def test_editor_access_matrix(async_client, editor_auth_headers) -> None:
    news_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news", headers=editor_auth_headers)
    media_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media", headers=editor_auth_headers)
    users_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users", headers=editor_auth_headers)

    assert news_response.status_code == status.HTTP_200_OK
    assert media_response.status_code == status.HTTP_200_OK
    assert users_response.status_code == status.HTTP_403_FORBIDDEN


async def test_operator_access_matrix(async_client, operator_auth_headers) -> None:
    matches_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches", headers=operator_auth_headers)
    news_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news", headers=operator_auth_headers)
    users_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users", headers=operator_auth_headers)

    assert matches_response.status_code == status.HTTP_200_OK
    assert news_response.status_code == status.HTTP_403_FORBIDDEN
    assert users_response.status_code == status.HTTP_403_FORBIDDEN


async def test_editor_cannot_finalize_match(async_client, editor_auth_headers) -> None:
    response = await async_client.post(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/finalize", headers=editor_auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_operator_can_update_match_score(async_client, operator_auth_headers) -> None:
    response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/score",
        headers=operator_auth_headers,
        json={"score_summary": "6-4 4-6 5-4", "sets": []},
    )
    assert response.status_code == status.HTTP_200_OK


async def test_operator_cannot_manage_media(async_client, operator_auth_headers) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media", headers=operator_auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_malformed_bearer_token_cannot_access_admin(async_client) -> None:
    response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users",
        headers={"Authorization": "Bearer definitely.invalid.token"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
