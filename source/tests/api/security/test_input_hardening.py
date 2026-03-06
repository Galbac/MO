from fastapi import status

from source.config.settings import settings


async def test_public_media_rejects_unsupported_content_type(async_client) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/media/upload",
        files={"file": ("malware.exe", b"binary", "application/octet-stream")},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_admin_media_rejects_oversized_payload(async_client, admin_auth_headers) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media/upload",
        json={"filename": "huge.txt", "content_type": "text/plain", "size": settings.media.max_upload_size_bytes + 1, "content": "x"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_news_html_is_sanitized(async_client, admin_auth_headers) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news",
        json={
            "slug": "sanitized-article",
            "title": "Sanitized article",
            "content_html": '<p onclick="alert(1)">Safe</p><script>alert(2)</script><a href="javascript:alert(3)">link</a>',
            "status": "draft",
        },
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    content_html = response.json()["data"]["content_html"]
    assert '<script' not in content_html.lower()
    assert 'onclick=' not in content_html.lower()
    assert 'javascript:' not in content_html.lower()
