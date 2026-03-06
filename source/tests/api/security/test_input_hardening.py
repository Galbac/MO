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
            "content_html": '<p onclick="alert(1)" style="color:red">Safe</p><script>alert(2)</script><iframe srcdoc="<script>alert(3)</script>"></iframe><a href="javascript:alert(4)">link</a>',
            "status": "draft",
        },
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    content_html = response.json()["data"]["content_html"]
    assert '<script' not in content_html.lower()
    assert 'onclick=' not in content_html.lower()
    assert 'javascript:' not in content_html.lower()
    assert '<iframe' not in content_html.lower()
    assert 'style=' not in content_html.lower()
    assert 'srcdoc=' not in content_html.lower()


async def test_public_media_rejects_unsafe_filename(async_client) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/media/upload",
        files={"file": ("../escape.txt", b"payload", "text/plain")},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_media_rejects_mismatched_extension(async_client) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/media/upload",
        files={"file": ("cover.jpg", b"plain text", "text/plain")},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_media_rejects_forbidden_extension(async_client, admin_auth_headers) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media/upload",
        json={"filename": "payload.html", "content_type": "text/plain", "content": "x"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

async def test_media_rejects_invalid_jpeg_signature(async_client) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/media/upload",
        files={"file": ("cover.jpg", b"not-a-jpeg", "image/jpeg")},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_admin_media_accepts_base64_png(async_client, admin_auth_headers) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media/upload",
        json={
            "filename": "cover.png",
            "content_type": "image/png",
            "content_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jk6sAAAAASUVORK5CYII=",
        },
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["data"]["filename"] == "cover.png"


async def test_media_rejects_filename_with_control_chars(async_client, admin_auth_headers) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media/upload",
        json={"filename": "bad\u0000name.txt", "content_type": "text/plain", "content": "x"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_media_rejects_windows_path_filename(async_client, admin_auth_headers) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media/upload",
        json={"filename": "..\\secret.txt", "content_type": "text/plain", "content": "x"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
