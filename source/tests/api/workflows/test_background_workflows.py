import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from source.config.settings import settings
from source.services import JobService


def _jobs_payload() -> list[dict]:
    path = Path(settings.jobs.storage_path)
    if not path.exists():
        return []
    return json.loads(path.read_text())


async def test_finalize_match_updates_h2h_and_creates_notification(async_client, user_auth_headers, admin_auth_headers) -> None:
    subscribe_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        headers=user_auth_headers,
        json={
            'entity_type': 'match',
            'entity_id': 2,
            'notification_types': ['match_finished'],
            'channels': ['web'],
        },
    )
    assert subscribe_response.status_code == 200

    finalize_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/finalize",
        headers=admin_auth_headers,
    )
    assert finalize_response.status_code == 200

    h2h_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/players/h2h",
        params={'player1_id': 3, 'player2_id': 4},
    )
    assert h2h_response.status_code == 200
    assert h2h_response.json()['data']['total_matches'] == 1
    assert h2h_response.json()['data']['last_match_id'] == 2

    notifications_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/notifications",
        headers=user_auth_headers,
    )
    assert notifications_response.status_code == 200
    assert any(item['type'] == 'match_finished' and item['payload_json']['entity_id'] == 2 for item in notifications_response.json()['data'])

    jobs = _jobs_payload()
    assert any(job['job_type'] == 'finalize_match_postprocess' and job['status'] == 'finished' for job in jobs)


async def test_scheduled_news_job_publishes_due_article(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news",
        headers=admin_auth_headers,
        json={
            'slug': 'scheduled-news-job',
            'title': 'Scheduled job article',
            'subtitle': 'Will be published by worker',
            'lead': 'Lead',
            'content_html': '<p>Scheduled content</p>',
            'status': 'draft',
            'category_id': 1,
        },
    )
    assert create_response.status_code == 200
    news_id = create_response.json()['data']['id']

    publish_at = (datetime.now(tz=UTC) - timedelta(minutes=1)).isoformat()
    schedule_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news/{news_id}/schedule",
        headers=admin_auth_headers,
        json={'status': 'scheduled', 'publish_at': publish_at},
    )
    assert schedule_response.status_code == 200

    processed = await JobService().process_due_jobs()
    assert processed >= 1

    article_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/news/scheduled-news-job")
    assert article_response.status_code == 200
    assert article_response.json()['data']['status'] == 'published'


async def test_match_status_change_creates_match_start_notification(async_client, user_auth_headers, admin_auth_headers) -> None:
    subscribe_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        headers=user_auth_headers,
        json={
            'entity_type': 'match',
            'entity_id': 2,
            'notification_types': ['match_start'],
            'channels': ['web'],
        },
    )
    assert subscribe_response.status_code == 200

    reset_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/status",
        headers=admin_auth_headers,
        json={'status': 'about_to_start'},
    )
    assert reset_response.status_code == 200

    update_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/status",
        headers=admin_auth_headers,
        json={'status': 'live'},
    )
    assert update_response.status_code == 200

    notifications_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/notifications",
        headers=user_auth_headers,
    )
    assert notifications_response.status_code == 200
    assert any(item['type'] == 'match_start' and item['payload_json']['entity_id'] == 2 for item in notifications_response.json()['data'])


async def test_match_start_notification_respects_quiet_hours(async_client, user_auth_headers, admin_auth_headers) -> None:
    update_profile = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me",
        headers=user_auth_headers,
        json={'timezone': 'UTC', 'quiet_hours_start': '00:00', 'quiet_hours_end': '23:59'},
    )
    assert update_profile.status_code == 200

    subscribe_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        headers=user_auth_headers,
        json={
            'entity_type': 'match',
            'entity_id': 2,
            'notification_types': ['match_start'],
            'channels': ['web'],
        },
    )
    assert subscribe_response.status_code == 200

    reset_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/status",
        headers=admin_auth_headers,
        json={'status': 'about_to_start'},
    )
    assert reset_response.status_code == 200

    update_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/status",
        headers=admin_auth_headers,
        json={'status': 'live'},
    )
    assert update_response.status_code == 200

    notifications_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/notifications",
        headers=user_auth_headers,
    )
    assert notifications_response.status_code == 200
    assert not any(item['type'] == 'match_start' and item['payload_json']['entity_id'] == 2 for item in notifications_response.json()['data'])


async def test_match_start_notification_skips_unsupported_active_channel(async_client, user_auth_headers, admin_auth_headers) -> None:
    subscribe_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        headers=user_auth_headers,
        json={
            'entity_type': 'match',
            'entity_id': 2,
            'notification_types': ['match_start'],
            'channels': ['email'],
        },
    )
    assert subscribe_response.status_code == 200

    reset_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/status",
        headers=admin_auth_headers,
        json={'status': 'about_to_start'},
    )
    assert reset_response.status_code == 200

    update_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/status",
        headers=admin_auth_headers,
        json={'status': 'live'},
    )
    assert update_response.status_code == 200

    notifications_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/notifications",
        headers=user_auth_headers,
    )
    assert notifications_response.status_code == 200
    assert not any(item['type'] == 'match_start' and item['payload_json']['entity_id'] == 2 for item in notifications_response.json()['data'])

async def test_maintenance_jobs_generate_artifacts(prepared_test_db: str) -> None:
    jobs = JobService()
    await jobs.enqueue(job_type='generate_sitemap', payload={'base_url': 'https://example.test'})
    await jobs.enqueue(job_type='rebuild_search_index')

    processed = await jobs.process_due_jobs()
    assert processed >= 2

    sitemap_path = Path(settings.maintenance.artifacts_dir) / 'sitemap_snapshot.json'
    search_index_path = Path(settings.maintenance.artifacts_dir) / 'search_index.json'

    assert sitemap_path.exists()
    assert search_index_path.exists()

    sitemap_payload = json.loads(sitemap_path.read_text())
    search_index_payload = json.loads(search_index_path.read_text())

    assert sitemap_payload['base_url'] == 'https://example.test'
    assert sitemap_payload['url_count'] >= 9
    assert any(url.endswith('/players/novak-djokovic') for url in sitemap_payload['urls'])
    assert search_index_payload['total_documents'] >= 4
    assert any(item['slug'] == 'novak-djokovic' for item in search_index_payload['players'])
