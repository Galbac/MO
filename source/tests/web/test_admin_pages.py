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



async def test_admin_audit_page_has_filter_controls(async_client) -> None:
    response = await async_client.get('/admin/audit')

    assert response.status_code == status.HTTP_200_OK
    assert 'id="admin-audit-filters"' in response.text
    assert 'id="audit-user-id"' in response.text
    assert 'id="audit-entity-type"' in response.text
    assert 'id="audit-action"' in response.text
    assert 'id="audit-date-from"' in response.text
    assert 'id="audit-date-to"' in response.text
    assert 'id="admin-audit-reset"' in response.text



async def test_admin_jobs_page_renders_html(async_client) -> None:
    response = await async_client.get('/admin/jobs')

    assert response.status_code == status.HTTP_200_OK
    assert 'Очередь задач' in response.text
    assert 'id="admin-jobs-process"' in response.text
    assert 'aria-label="Таблица очереди задач"' in response.text



async def test_admin_maintenance_page_renders_html(async_client) -> None:
    response = await async_client.get('/admin/maintenance')

    assert response.status_code == status.HTTP_200_OK
    assert 'Maintenance' in response.text
    assert 'data-maintenance-run="generate_sitemap"' in response.text
    assert 'aria-label="Таблица maintenance артефактов"' in response.text



async def test_admin_dashboard_links_operations_views(async_client) -> None:
    response = await async_client.get('/admin')

    assert response.status_code == status.HTTP_200_OK
    assert '/admin/jobs' in response.text
    assert '/admin/maintenance' in response.text
    assert 'id="admin-jobs-count"' in response.text



async def test_admin_tournaments_page_has_lifecycle_actions(async_client) -> None:
    response = await async_client.get('/admin/tournaments')

    assert response.status_code == status.HTTP_200_OK
    assert 'data-tournament-draw' in response.text or 'Действия' in response.text



async def test_admin_players_page_has_import_and_actions(async_client) -> None:
    response = await async_client.get('/admin/players')

    assert response.status_code == status.HTTP_200_OK
    assert 'id="admin-player-import-form"' in response.text
    assert 'id="admin-player-import-json"' in response.text
    assert 'Действия' in response.text



async def test_admin_news_page_has_cover_and_tags_actions(async_client) -> None:
    response = await async_client.get('/admin/news')

    assert response.status_code == status.HTTP_200_OK
    assert 'Действия' in response.text



async def test_admin_users_page_has_action_column(async_client) -> None:
    response = await async_client.get('/admin/users')

    assert response.status_code == status.HTTP_200_OK
    assert 'Действия' in response.text
