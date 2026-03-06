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


async def test_admin_list_pages_include_accessible_landmarks(async_client) -> None:
    players = await async_client.get('/admin/players')
    matches = await async_client.get('/admin/matches')
    tournaments = await async_client.get('/admin/tournaments')
    audit = await async_client.get('/admin/audit')

    assert 'href="#admin-main-content"' in players.text
    assert 'aria-label="Таблица игроков"' in players.text

    assert 'href="#admin-main-content"' in matches.text
    assert 'aria-label="Таблица матчей"' in matches.text

    assert 'href="#admin-main-content"' in tournaments.text
    assert 'aria-label="Таблица турниров"' in tournaments.text

    assert 'href="#admin-main-content"' in audit.text
    assert 'aria-label="Таблица аудита"' in audit.text
