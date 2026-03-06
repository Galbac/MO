from fastapi import status

from source.config.settings import settings


async def test_auth_me_returns_success(async_client, user_auth_headers) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/auth/me", headers=user_auth_headers)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["username"] == "demo_user"


async def test_register_creates_user_and_returns_tokens(async_client) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/register",
        json={
            "email": "new-user@example.com",
            "username": "new_user",
            "password": "StrongPass123",
            "locale": "en",
            "timezone": "UTC",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["user"]["email"] == "new-user@example.com"
    assert payload["data"]["access_token"]


async def test_login_returns_db_backed_user(async_client) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={"email_or_username": "demo_user", "password": "UserPass123"},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]["user"]["username"] == "demo_user"
    assert payload["data"]["refresh_token"]
