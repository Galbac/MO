from fastapi import status


async def test_admin_media_page_renders_html(async_client) -> None:
    response = await async_client.get("/admin/media")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Media library" in response.text


async def test_admin_notifications_page_renders_html(async_client) -> None:
    response = await async_client.get("/admin/notifications")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Templates" in response.text
