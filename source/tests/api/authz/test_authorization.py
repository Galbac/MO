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
