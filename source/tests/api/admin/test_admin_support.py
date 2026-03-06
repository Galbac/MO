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


async def test_admin_rankings_provider_import_updates_current_snapshot(async_client, admin_auth_headers) -> None:
    import_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/rankings/import",
        json={
            'provider': 'rankings-provider',
            'provider_payload': {
                'ranking_type': 'atp',
                'ranking_date': '2026-03-10',
                'entries': [
                    {'position': 1, 'player_name': 'Jannik Sinner', 'country_code': 'IT', 'points': 9100},
                    {'position': 2, 'player_name': 'Novak Djokovic', 'country_code': 'RS', 'points': 8700},
                ],
            },
        },
        headers=admin_auth_headers,
    )
    assert import_response.status_code == status.HTTP_200_OK

    rankings_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/rankings/current?ranking_type=atp")
    assert rankings_response.status_code == status.HTTP_200_OK
    assert rankings_response.json()['data'][0]['player_name'] == 'Jannik Sinner'
    assert rankings_response.json()['data'][0]['ranking_date'] == '2026-03-10'

import json
from pathlib import Path


async def test_admin_rankings_recalculate_movements_and_player_notifications(async_client, user_auth_headers, admin_auth_headers) -> None:
    subscribe_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        headers=user_auth_headers,
        json={
            'entity_type': 'player',
            'entity_id': 1,
            'notification_types': ['ranking_change'],
            'channels': ['web'],
        },
    )
    assert subscribe_response.status_code in {status.HTTP_200_OK, status.HTTP_409_CONFLICT}

    import_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/rankings/import",
        json={
            'provider': 'rankings-provider',
            'provider_payload': {
                'ranking_type': 'atp',
                'ranking_date': '2026-03-11',
                'entries': [
                    {'position': 1, 'player_name': 'Jannik Sinner', 'country_code': 'IT', 'points': 9200, 'movement': 1},
                    {'position': 2, 'player_name': 'Novak Djokovic', 'country_code': 'RS', 'points': 9100, 'movement': -1},
                ],
            },
        },
        headers=admin_auth_headers,
    )
    assert import_response.status_code == status.HTTP_200_OK

    recalc_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/rankings/recalculate-movements",
        headers=admin_auth_headers,
    )
    assert recalc_response.status_code == status.HTTP_200_OK
    assert recalc_response.json()['data']['message'] == 'Ranking movements recalculated'

    current_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/rankings/current?ranking_type=atp")
    assert current_response.status_code == status.HTTP_200_OK
    current_rows = current_response.json()['data']
    assert current_rows[0]['player_name'] == 'Jannik Sinner'
    assert abs(current_rows[0]['movement']) >= 1

    notifications_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/notifications",
        headers=user_auth_headers,
    )
    assert notifications_response.status_code == status.HTTP_200_OK
    assert any(item['type'] == 'ranking_change' and item['payload_json']['entity_id'] == 1 for item in notifications_response.json()['data'])

    history_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/notifications", headers=admin_auth_headers)
    assert history_response.status_code == status.HTTP_200_OK
    assert any(item['title'] == 'Ranking update: Novak Djokovic' for item in history_response.json()['data'])


async def test_admin_rankings_import_clears_players_missing_from_latest_snapshot(async_client, admin_auth_headers) -> None:
    import_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/rankings/import",
        json={
            'provider': 'rankings-provider',
            'provider_payload': {
                'ranking_type': 'atp',
                'ranking_date': '2026-03-12',
                'entries': [
                    {'position': 1, 'player_name': 'Jannik Sinner', 'country_code': 'IT', 'points': 9300},
                ],
            },
        },
        headers=admin_auth_headers,
    )
    assert import_response.status_code == status.HTTP_200_OK

    missing_player_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/players/1")
    assert missing_player_response.status_code == status.HTTP_200_OK
    missing_player = missing_player_response.json()['data']
    assert missing_player['current_rank'] is None
    assert missing_player['current_points'] is None

    still_ranked_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/players/2")
    assert still_ranked_response.status_code == status.HTTP_200_OK
    still_ranked = still_ranked_response.json()['data']
    assert still_ranked['current_rank'] == 1
    assert still_ranked['current_points'] == 9300
