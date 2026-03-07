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
        json={"first_name": "Updated", "timezone": "UTC", "quiet_hours_start": "23:00", "quiet_hours_end": "07:00"},
        headers=user_auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["data"]["first_name"] == "Updated"
    assert payload["data"]["timezone"] == "UTC"
    assert payload["data"]["quiet_hours_start"] == "23:00"
    assert payload["data"]["quiet_hours_end"] == "07:00"


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


async def test_subscriptions_reject_invalid_channel(async_client, user_auth_headers) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        json={
            "entity_type": "match",
            "entity_id": 2,
            "notification_types": ["match_start"],
            "channels": ["sms"],
        },
        headers=user_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_subscriptions_reject_invalid_notification_type(async_client, user_auth_headers) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        json={
            "entity_type": "match",
            "entity_id": 2,
            "notification_types": ["unknown_type"],
            "channels": ["web"],
        },
        headers=user_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_user_calendar_and_reminders_flow(async_client, user_auth_headers) -> None:
    calendar_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/calendar", headers=user_auth_headers)
    assert calendar_response.status_code == status.HTTP_200_OK
    assert "items" in calendar_response.json()["data"]

    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/calendar/reminders",
        json={"match_id": 2, "remind_before_minutes": 45, "channel": "web"},
        headers=user_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    reminder_id = create_response.json()["data"]["id"]
    assert create_response.json()["data"]["match_id"] == 2

    update_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/calendar/reminders/{reminder_id}",
        json={"remind_before_minutes": 60, "is_active": False},
        headers=user_auth_headers,
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["data"]["remind_before_minutes"] == 60
    assert update_response.json()["data"]["is_active"] is False

    delete_response = await async_client.delete(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/calendar/reminders/{reminder_id}",
        headers=user_auth_headers,
    )
    assert delete_response.status_code == status.HTTP_200_OK


async def test_user_smart_feed_and_push_subscription_flow(async_client, user_auth_headers) -> None:
    feed_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/smart-feed", headers=user_auth_headers)
    assert feed_response.status_code == status.HTTP_200_OK
    assert "players" in feed_response.json()["data"]
    assert "tournaments" in feed_response.json()["data"]

    list_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/push-subscriptions", headers=user_auth_headers)
    assert list_response.status_code == status.HTTP_200_OK

    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/push-subscriptions",
        json={
            "endpoint": "browser://test/device-1",
            "device_label": "pytest-browser",
            "keys_json": {"auth": "token"},
            "permission": "granted",
        },
        headers=user_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    subscription_id = create_response.json()["data"]["id"]

    test_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/push-subscriptions/test",
        json={"title": "Проверка", "body": "Push канал активен"},
        headers=user_auth_headers,
    )
    assert test_response.status_code == status.HTTP_200_OK
    assert test_response.json()["data"]["details"]["active_devices"] >= 1

    delete_response = await async_client.delete(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/push-subscriptions/{subscription_id}",
        headers=user_auth_headers,
    )
    assert delete_response.status_code == status.HTTP_200_OK
