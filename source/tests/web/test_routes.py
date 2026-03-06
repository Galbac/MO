from fastapi import status


async def test_home_page_renders_html(async_client) -> None:
    response = await async_client.get("/")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Makhachkala Open" in response.text
    assert "Начните с регистрации" in response.text
    assert "Согласие на обработку данных" in response.text


async def test_portal_page_renders_html(async_client) -> None:
    response = await async_client.get("/portal", follow_redirects=False)

    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert response.headers["location"].startswith("/register")


async def test_portal_page_renders_html_for_authenticated_user(user_session_client) -> None:
    response = await user_session_client.get("/portal")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Счета, новости и рейтинги" in response.text


async def test_admin_dashboard_renders_html(async_client) -> None:
    response = await async_client.get("/admin", follow_redirects=False)

    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert response.headers["location"].startswith("/admin/login")


async def test_admin_dashboard_renders_html_for_admin(admin_session_client) -> None:
    response = await admin_session_client.get("/admin")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Админка" in response.text
    assert "Панель" in response.text


async def test_h2h_page_renders_html(user_session_client) -> None:
    response = await user_session_client.get("/h2h")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Личные встречи" in response.text


async def test_error_pages_render_html(async_client) -> None:
    response_404 = await async_client.get("/404")
    response_500 = await async_client.get("/500")

    assert response_404.status_code == status.HTTP_200_OK
    assert response_500.status_code == status.HTTP_200_OK
    assert "Страница не найдена" in response_404.text
    assert "Что-то пошло не так" in response_500.text


async def test_robots_and_sitemap_are_exposed(async_client) -> None:
    robots = await async_client.get('/robots.txt')
    sitemap = await async_client.get('/sitemap.xml')

    assert robots.status_code == status.HTTP_200_OK
    assert 'Sitemap:' in robots.text
    assert sitemap.status_code == status.HTTP_200_OK
    assert '<urlset' in sitemap.text
    assert '/players/novak-djokovic' in sitemap.text


async def test_search_page_includes_seo_meta(user_session_client) -> None:
    response = await user_session_client.get('/search')

    assert response.status_code == status.HTTP_200_OK
    assert 'meta name="description"' in response.text
    assert 'property="og:title"' in response.text
    assert 'rel="canonical"' in response.text


async def test_rankings_page_renders_both_tours(user_session_client) -> None:
    response = await user_session_client.get("/rankings")

    assert response.status_code == status.HTTP_200_OK
    assert "Рейтинг ATP" in response.text
    assert "Рейтинг WTA" in response.text


async def test_detail_pages_include_structured_data(user_session_client) -> None:
    player = await user_session_client.get('/players/novak-djokovic')
    match = await user_session_client.get('/matches/djokovic-vs-sinner-ao-2026-final')
    article = await user_session_client.get('/news/djokovic-wins-ao-2026')

    assert player.status_code == status.HTTP_200_OK
    assert 'application/ld+json' in player.text
    assert 'Novak Djokovic' in player.text
    assert 'property="og:image"' in player.text

    assert match.status_code == status.HTTP_200_OK
    assert 'SportsEvent' in match.text
    assert 'Novak Djokovic vs Jannik Sinner' in match.text

    assert article.status_code == status.HTTP_200_OK
    assert 'NewsArticle' in article.text
    assert 'property="og:type" content="article"' in article.text


async def test_layouts_include_skip_links_and_landmarks(async_client) -> None:
    public_response = await async_client.get('/')
    admin_response = await async_client.get('/admin', follow_redirects=False)

    assert public_response.status_code == status.HTTP_200_OK
    assert 'skip-link' in public_response.text
    assert 'href="#main-content"' in public_response.text
    assert 'aria-label="Основная навигация"' in public_response.text
    assert 'role="main"' in public_response.text

    assert admin_response.status_code == status.HTTP_303_SEE_OTHER
    assert admin_response.headers["location"].startswith("/admin/login")


async def test_list_pages_include_accessible_navigation_and_tables(user_session_client, admin_session_client) -> None:
    players = await user_session_client.get('/players')
    matches = await user_session_client.get('/matches')
    admin_users = await admin_session_client.get('/admin/users')
    admin_news = await admin_session_client.get('/admin/news')

    assert 'aria-label="Фильтр по стране"' in players.text
    assert 'aria-label="Поиск игроков"' in players.text
    assert 'href="#main-content"' in matches.text
    assert 'aria-label="Фильтр по статусу матча"' in matches.text
    assert 'aria-label="Таблица пользователей"' in admin_users.text
    assert 'href="#admin-main-content"' in admin_news.text
    assert 'aria-label="Таблица новостей"' in admin_news.text


async def test_detail_pages_include_accessible_landmarks(user_session_client) -> None:
    player = await user_session_client.get('/players/novak-djokovic')
    match = await user_session_client.get('/matches/djokovic-vs-sinner-ao-2026-final')
    news = await user_session_client.get('/news/djokovic-wins-ao-2026')

    assert 'href="#main-content"' in player.text
    assert 'role="main"' in player.text
    assert 'aria-label="История рейтинга игрока"' in player.text

    assert 'href="#main-content"' in match.text
    assert 'aria-label="Статистика матча"' in match.text

    assert 'href="#main-content"' in news.text
    assert 'aria-label="Основная навигация"' in news.text


async def test_additional_public_pages_include_accessible_filters(user_session_client) -> None:
    tournaments = await user_session_client.get('/tournaments')
    live = await user_session_client.get('/live')
    news = await user_session_client.get('/news')
    h2h = await user_session_client.get('/h2h')
    tournament_detail = await user_session_client.get('/tournaments/australian-open-2026')

    assert 'href="#main-content"' in tournaments.text
    assert 'aria-label="Фильтр по сезону"' in tournaments.text
    assert 'aria-label="Фильтр по категории турнира"' in tournaments.text

    assert 'href="#main-content"' in live.text
    assert 'aria-label="Основная навигация"' in live.text

    assert 'href="#main-content"' in news.text
    assert 'aria-label="Фильтр по категории новостей"' in news.text
    assert 'aria-label="Поиск новостей"' in news.text

    assert 'href="#main-content"' in h2h.text
    assert 'aria-label="Выбор первого игрока"' in h2h.text
    assert 'aria-label="Статистика личных встреч по покрытиям"' in h2h.text

    assert 'href="#main-content"' in tournament_detail.text
    assert 'aria-label="Основная навигация"' in tournament_detail.text



async def test_player_detail_page_mentions_extended_season_stats(user_session_client) -> None:
    response = await user_session_client.get('/players/novak-djokovic')

    assert response.status_code == 200
    assert 'Статистика сезона и форма' in response.text


async def test_public_list_pages_have_state_placeholders(user_session_client) -> None:
    tournaments = await user_session_client.get('/tournaments')
    matches = await user_session_client.get('/matches')
    news = await user_session_client.get('/news')
    search = await user_session_client.get('/search')
    notifications = await user_session_client.get('/notifications')

    assert 'id="tournaments-error"' in tournaments.text
    assert 'id="tournaments-empty"' in tournaments.text
    assert 'id="matches-error"' in matches.text
    assert 'id="matches-empty"' in matches.text
    assert 'id="news-list-error"' in news.text
    assert 'id="news-list-empty"' in news.text
    assert 'id="search-error"' in search.text
    assert 'id="search-empty"' in search.text
    assert 'id="notifications-error"' in notifications.text
    assert 'id="notifications-empty"' in notifications.text


async def test_live_rankings_account_pages_have_state_placeholders(user_session_client) -> None:
    live = await user_session_client.get('/live')
    rankings = await user_session_client.get('/rankings')
    account = await user_session_client.get('/account')

    assert 'id="live-matches-error"' in live.text
    assert 'id="live-matches-empty"' in live.text
    assert 'id="live-feed-error"' in live.text
    assert 'id="rankings-error"' in rankings.text
    assert 'id="rankings-empty"' in rankings.text
    assert 'id="account-error"' in account.text
    assert 'id="account-favorites-empty"' in account.text
    assert 'id="account-subscriptions-empty"' in account.text


async def test_guest_is_redirected_from_protected_public_pages(async_client) -> None:
    response = await async_client.get('/players', follow_redirects=False)

    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert response.headers["location"].startswith('/register')


async def test_non_admin_is_redirected_from_admin_pages(user_session_client) -> None:
    response = await user_session_client.get('/admin/users', follow_redirects=False)

    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert response.headers["location"] == '/portal'
