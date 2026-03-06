from fastapi import status


async def test_home_page_renders_html(async_client) -> None:
    response = await async_client.get("/")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Tennis Portal" in response.text


async def test_admin_dashboard_renders_html(async_client) -> None:
    response = await async_client.get("/admin")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Admin" in response.text


async def test_h2h_page_renders_html(async_client) -> None:
    response = await async_client.get("/h2h")

    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers["content-type"]
    assert "Head to head" in response.text


async def test_error_pages_render_html(async_client) -> None:
    response_404 = await async_client.get("/404")
    response_500 = await async_client.get("/500")

    assert response_404.status_code == status.HTTP_200_OK
    assert response_500.status_code == status.HTTP_200_OK
    assert "Page not found" in response_404.text
    assert "Something went wrong" in response_500.text
