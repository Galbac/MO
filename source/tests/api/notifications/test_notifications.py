from fastapi import status

from source.config.settings import settings


async def test_notifications_endpoints_use_db_backed_data(async_client, user_auth_headers) -> None:
    list_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/notifications", headers=user_auth_headers)
    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.json()["data"]) >= 1

    unread_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/notifications/unread-count", headers=user_auth_headers)
    assert unread_response.status_code == status.HTTP_200_OK
    assert unread_response.json()["data"]["unread_count"] >= 1


async def test_test_notification_creates_new_notification(async_client, user_auth_headers) -> None:
    create_response = await async_client.post(f"{settings.api.prefix}{settings.api.v1.prefix}/notifications/test", headers=user_auth_headers)
    assert create_response.status_code == status.HTTP_200_OK
    assert create_response.json()["data"]["message"] == "Test notification sent"

    list_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/notifications", headers=user_auth_headers)
    assert any(item["type"] == "test" for item in list_response.json()["data"])
