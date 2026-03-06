from fastapi import status

from source.config.settings import settings


async def test_users_me_returns_seeded_demo_user(async_client, user_auth_headers) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me", headers=user_auth_headers)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]["username"] == "demo_user"


async def test_patch_users_me_updates_profile(async_client, user_auth_headers) -> None:
    response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me",
        json={"first_name": "Updated", "timezone": "UTC"},
        headers=user_auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]["first_name"] == "Updated"
    assert payload["data"]["timezone"] == "UTC"


async def test_patch_users_me_password_changes_hash(async_client, user_auth_headers) -> None:
    response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/password",
        json={"current_password": "UserPass123", "new_password": "NewPass456"},
        headers=user_auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]["message"] == "Password changed and tokens revoked"


async def test_favorites_crud_flow(async_client, user_auth_headers) -> None:
    list_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/favorites", headers=user_auth_headers)
    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.json()["data"]) >= 2

    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/favorites",
        json={"entity_type": "news", "entity_id": 1},
        headers=user_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    favorite_id = create_response.json()["data"]["id"]

    delete_response = await async_client.delete(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/favorites/{favorite_id}", headers=user_auth_headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert delete_response.json()["data"]["message"] == "Favorite deleted"


async def test_subscriptions_crud_flow(async_client, user_auth_headers) -> None:
    list_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions", headers=user_auth_headers)
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["data"][0]["entity_type"] == "player"

    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        json={
            "entity_type": "match",
            "entity_id": 2,
            "notification_types": ["match_start"],
            "channels": ["web"],
        },
        headers=user_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    subscription_id = create_response.json()["data"]["id"]

    update_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions/{subscription_id}",
        json={"is_active": False},
        headers=user_auth_headers,
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["data"]["is_active"] is False

    delete_response = await async_client.delete(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions/{subscription_id}", headers=user_auth_headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert delete_response.json()["data"]["message"] == "Subscription deleted"


async def test_user_notifications_flow(async_client, user_auth_headers) -> None:
    list_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/notifications", headers=user_auth_headers)
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["data"][0]["title"]

    read_response = await async_client.patch(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/notifications/1/read", headers=user_auth_headers)
    assert read_response.status_code == status.HTTP_200_OK
    assert read_response.json()["data"]["status"] == "read"

    read_all_response = await async_client.patch(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/notifications/read-all", headers=user_auth_headers)
    assert read_all_response.status_code == status.HTTP_200_OK
    assert read_all_response.json()["data"]["message"] == "All notifications marked as read"
