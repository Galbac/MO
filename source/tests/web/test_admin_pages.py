from fastapi import status


async def test_admin_media_page_renders_html(async_client) -> None:
    response = await async_client.get("/admin/media")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Медиатека" in response.text


async def test_admin_notifications_page_renders_html(async_client) -> None:
    response = await async_client.get("/admin/notifications")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Шаблоны" in response.text


async def test_admin_live_operations_page_has_dynamic_match_selector(async_client) -> None:
    response = await async_client.get("/admin/live-operations")

    assert response.status_code == status.HTTP_200_OK
    assert "admin-live-match-id" in response.text
    assert "/admin/matches/2/events" not in response.text


async def test_admin_media_page_uses_safe_text_defaults(async_client) -> None:
    response = await async_client.get("/admin/media")

    assert response.status_code == status.HTTP_200_OK
    assert "name=\"filename\"" in response.text
    assert "note.txt" in response.text
    assert "text/plain" in response.text
    assert "name=\"content\"" in response.text
