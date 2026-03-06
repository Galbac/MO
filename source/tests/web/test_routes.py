from fastapi import status


async def test_home_page_renders_html(async_client) -> None:
    response = await async_client.get("/")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Makhachkala Open" in response.text
    assert "Счета, новости и рейтинги" in response.text


async def test_admin_dashboard_renders_html(async_client) -> None:
    response = await async_client.get("/admin")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Админка" in response.text
    assert "Панель" in response.text


async def test_h2h_page_renders_html(async_client) -> None:
    response = await async_client.get("/h2h")

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


async def test_search_page_includes_seo_meta(async_client) -> None:
    response = await async_client.get('/search')

    assert response.status_code == status.HTTP_200_OK
    assert 'meta name="description"' in response.text
    assert 'property="og:title"' in response.text
    assert 'rel="canonical"' in response.text
