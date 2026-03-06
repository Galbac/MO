from fastapi import status

from source.config.settings import settings


async def test_admin_settings_persist(async_client, admin_auth_headers) -> None:
    patch_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/settings",
        json={"seo_title": "Portal SEO", "support_email": "support@example.com"},
        headers=admin_auth_headers,
    )
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.json()["data"]["seo_title"] == "Portal SEO"

    get_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/settings", headers=admin_auth_headers)
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["data"]["support_email"] == "support@example.com"


async def test_admin_taxonomy_crud(async_client, admin_auth_headers) -> None:
    create_category = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news-categories",
        json={"name": "Features", "slug": "features"},
        headers=admin_auth_headers,
    )
    assert create_category.status_code == status.HTTP_200_OK

    categories_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news-categories", headers=admin_auth_headers)
    category_id = next(item["id"] for item in categories_response.json()["data"] if item["slug"] == "features")

    update_category = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news-categories/{category_id}",
        json={"name": "Deep Features", "slug": "deep-features"},
        headers=admin_auth_headers,
    )
    assert update_category.status_code == status.HTTP_200_OK

    create_tag = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tags",
        json={"name": "Live Blog", "slug": "live-blog"},
        headers=admin_auth_headers,
    )
    assert create_tag.status_code == status.HTTP_200_OK

    tags_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tags", headers=admin_auth_headers)
    tag_id = next(item["id"] for item in tags_response.json()["data"] if item["slug"] == "live-blog")

    delete_tag = await async_client.delete(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tags/{tag_id}", headers=admin_auth_headers)
    assert delete_tag.status_code == status.HTTP_200_OK


async def test_admin_notifications_and_rankings(async_client, admin_auth_headers) -> None:
    templates_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/notifications/templates", headers=admin_auth_headers)
    assert templates_response.status_code == status.HTTP_200_OK
    assert templates_response.json()["data"]

    test_notification = await async_client.post(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/notifications/test", headers=admin_auth_headers)
    assert test_notification.status_code == status.HTTP_200_OK

    history_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/notifications", headers=admin_auth_headers)
    assert history_response.status_code == status.HTTP_200_OK
    assert history_response.json()["data"]

    import_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/rankings/import",
        json={"source_file": "ranking_snapshot.csv"},
        headers=admin_auth_headers,
    )
    assert import_response.status_code == status.HTTP_200_OK

    jobs_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/rankings/import-jobs", headers=admin_auth_headers)
    assert jobs_response.status_code == status.HTTP_200_OK
    assert jobs_response.json()["data"]
