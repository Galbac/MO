from fastapi import status

from source.config.settings import settings


async def test_admin_media_returns_library(async_client, admin_auth_headers) -> None:
    upload_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media/upload",
        json={"filename": "note.txt", "content_type": "text/plain", "content": "preview"},
        headers=admin_auth_headers,
    )
    assert upload_response.status_code == status.HTTP_201_CREATED

    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media", headers=admin_auth_headers)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"][0]["filename"] == "note.txt"


async def test_admin_notifications_returns_history(async_client, admin_auth_headers) -> None:
    response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/notifications", headers=admin_auth_headers)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"][0]["status"] in {"sent", "queued"}
