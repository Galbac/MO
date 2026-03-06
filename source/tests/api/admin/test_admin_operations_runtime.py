from fastapi import status

from source.config.settings import settings


async def test_media_and_audit_runtime(async_client, admin_auth_headers) -> None:
    admin_upload = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media/upload",
        json={"filename": "cover.jpg", "content_type": "image/jpeg", "content": "binary-image"},
        headers=admin_auth_headers,
    )
    assert admin_upload.status_code == status.HTTP_201_CREATED
    media_id = admin_upload.json()["data"]["id"]

    media_list = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media", headers=admin_auth_headers)
    assert media_list.status_code == status.HTTP_200_OK
    assert any(item["id"] == media_id for item in media_list.json()["data"])

    audit_list = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/audit-logs", headers=admin_auth_headers)
    assert audit_list.status_code == status.HTTP_200_OK
    assert audit_list.json()["data"]

    audit_id = audit_list.json()["data"][0]["id"]
    audit_detail = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/audit-logs/{audit_id}", headers=admin_auth_headers)
    assert audit_detail.status_code == status.HTTP_200_OK

    delete_response = await async_client.delete(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media/{media_id}", headers=admin_auth_headers)
    assert delete_response.status_code == status.HTTP_200_OK


async def test_public_media_upload_runtime(async_client) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/media/upload",
        files={"file": ("story.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == status.HTTP_201_CREATED
    media_id = response.json()["data"]["id"]

    get_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/media/{media_id}")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["data"]["filename"] == "story.txt"


async def test_integrations_runtime(async_client, admin_auth_headers) -> None:
    patch_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider",
        json={"api_key": "secret", "endpoint": "https://example.invalid"},
        headers=admin_auth_headers,
    )
    assert patch_response.status_code == status.HTTP_200_OK

    sync_response = await async_client.post(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/sync", headers=admin_auth_headers)
    assert sync_response.status_code == status.HTTP_200_OK

    list_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations", headers=admin_auth_headers)
    assert list_response.status_code == status.HTTP_200_OK
    assert any(item["provider"] == "live-provider" for item in list_response.json()["data"])

    logs_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/logs", headers=admin_auth_headers)
    assert logs_response.status_code == status.HTTP_200_OK
    assert "Manual sync executed" in logs_response.json()["data"]["message"]
