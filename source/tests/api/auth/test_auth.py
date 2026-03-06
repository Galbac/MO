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
            "privacy_consent": True,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["user"]["email"] == "new-user@example.com"
    assert payload["data"]["access_token"]
    assert "mo_access_token=" in response.headers.get("set-cookie", "")


async def test_login_returns_db_backed_user(async_client) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={"email_or_username": "demo_user", "password": "UserPass123"},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]["user"]["username"] == "demo_user"
    assert payload["data"]["refresh_token"]
    assert "mo_access_token=" in response.headers.get("set-cookie", "")


async def test_refresh_token_rotation_invalidates_old_refresh(async_client) -> None:
    login_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={"email_or_username": "demo_user", "password": "UserPass123"},
    )
    assert login_response.status_code == status.HTTP_200_OK
    refresh_token = login_response.json()["data"]["refresh_token"]

    refresh_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == status.HTTP_200_OK

    reused_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert reused_response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_forgot_password_reset_flow_updates_password(async_client) -> None:
    from source.services.auth_user_service import AuthUserService

    service = AuthUserService()
    forgot_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/forgot-password",
        json={"email": settings.demo.user_email},
    )

    assert forgot_response.status_code == status.HTTP_200_OK
    action_store = service.store.read_namespace(service.action_token_namespace, {})
    _, token_record = next(
        (token_id, record)
        for token_id, record in action_store.items()
        if record.get("purpose") == "password_reset" and record.get("used") is False
    )
    assert token_record["user_id"] == 2

    reset_token = service._issue_action_token(
        user_id=token_record["user_id"],
        purpose="password_reset",
        ttl_minutes=settings.auth.password_reset_token_ttl_minutes,
    )
    reset_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/reset-password",
        json={"token": reset_token, "new_password": "UserPass456"},
    )

    assert reset_response.status_code == status.HTTP_200_OK
    reused_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/reset-password",
        json={"token": reset_token, "new_password": "UserPass789"},
    )
    assert reused_response.status_code == status.HTTP_401_UNAUTHORIZED

    login_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={"email_or_username": "demo_user", "password": "UserPass456"},
    )
    assert login_response.status_code == status.HTTP_200_OK


async def test_verify_email_marks_user_verified(async_client) -> None:
    from source.services.auth_user_service import AuthUserService

    register_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/register",
        json={
            "email": "verify-me@example.com",
            "username": "verify_me",
            "password": "StrongPass123",
            "locale": "ru",
            "timezone": "Europe/Moscow",
            "privacy_consent": True,
        },
    )
    assert register_response.status_code == status.HTTP_201_CREATED

    service = AuthUserService()
    action_store = service.store.read_namespace(service.action_token_namespace, {})
    verify_token = None
    for token_id, record in action_store.items():
        if record.get("purpose") != "verify_email" or record.get("used") is not False:
            continue
        if int(record.get("user_id", 0)) == register_response.json()["data"]["user"]["id"]:
            verify_token = service._issue_action_token(
                user_id=record["user_id"],
                purpose="verify_email",
                ttl_minutes=settings.auth.email_verification_token_ttl_minutes,
            )
            break
    assert verify_token is not None

    verify_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/verify-email",
        json={"token": verify_token},
    )
    assert verify_response.status_code == status.HTTP_200_OK

    login_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={"email_or_username": "verify_me", "password": "StrongPass123"},
    )
    assert login_response.status_code == status.HTTP_200_OK
    assert login_response.json()["data"]["user"]["is_email_verified"] is True


async def test_login_bruteforce_is_rate_limited(async_client) -> None:
    for _ in range(5):
        response = await async_client.post(
            f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
            json={"email_or_username": "demo_user", "password": "wrong-password"},
        )
        assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_429_TOO_MANY_REQUESTS}

    locked_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={"email_or_username": "demo_user", "password": "UserPass123"},
    )
    assert locked_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
