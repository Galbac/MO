from fastapi import status

from source.config.settings import settings


async def test_admin_end_to_end_journey(async_client, admin_auth_headers) -> None:
    dashboard_response = await async_client.get('/admin')
    assert dashboard_response.status_code == status.HTTP_200_OK

    create_news = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news",
        headers=admin_auth_headers,
        json={
            'slug': 'e2e-admin-article',
            'title': 'E2E admin article',
            'subtitle': 'Published from journey',
            'lead': 'Lead',
            'content_html': '<p>Body</p>',
            'status': 'draft',
            'category_id': 1,
        },
    )
    assert create_news.status_code == status.HTTP_200_OK
    news_id = create_news.json()['data']['id']

    publish_news = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news/{news_id}/publish",
        headers=admin_auth_headers,
    )
    assert publish_news.status_code == status.HTTP_200_OK

    public_news = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/news/e2e-admin-article")
    assert public_news.status_code == status.HTTP_200_OK
    assert public_news.json()['data']['status'] == 'published'

    score_update = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/score",
        headers=admin_auth_headers,
        json={'score_summary': '6-4 4-6 5-2', 'sets': []},
    )
    assert score_update.status_code == status.HTTP_200_OK

    finalize = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/finalize",
        headers=admin_auth_headers,
    )
    assert finalize.status_code == status.HTTP_200_OK

    match_detail = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/matches/2")
    assert match_detail.status_code == status.HTTP_200_OK
    assert match_detail.json()['data']['status'] == 'finished'


async def test_editor_and_operator_journeys(async_client, editor_auth_headers, operator_auth_headers) -> None:
    editor_news = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news", headers=editor_auth_headers)
    assert editor_news.status_code == status.HTTP_200_OK

    editor_users = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users", headers=editor_auth_headers)
    assert editor_users.status_code == status.HTTP_403_FORBIDDEN

    operator_matches = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/score",
        headers=operator_auth_headers,
        json={"score_summary": "6-4 4-6 5-4", "sets": []},
    )
    assert operator_matches.status_code == status.HTTP_200_OK

    operator_news = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news", headers=operator_auth_headers)
    assert operator_news.status_code == status.HTTP_403_FORBIDDEN
