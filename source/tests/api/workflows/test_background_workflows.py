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

    aggregates_path = Path(settings.maintenance.artifacts_dir) / 'player_aggregates.json'
    assert aggregates_path.exists()
    aggregates_payload = json.loads(aggregates_path.read_text())
    medvedev = aggregates_payload['players']['3']
    rublev = aggregates_payload['players']['4']
    assert medvedev['stats']['wins'] == 1
    assert medvedev['stats']['hard_record'] == '1-0'
    assert medvedev['form'][:1] == ['W']
    assert rublev['stats']['losses'] == 1
    assert rublev['stats']['hard_record'] == '0-1'


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


async def test_match_start_email_channel_writes_delivery_log(async_client, user_auth_headers, admin_auth_headers, monkeypatch) -> None:
    monkeypatch.setattr(settings.notifications, 'active_channels', ['web', 'email'])
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

    delivery_log = Path(settings.notifications.delivery_log_path)
    assert delivery_log.exists()
    payload = json.loads(delivery_log.read_text())
    assert any(item['channel'] == 'email' and item['notification_type'] == 'match_start' and item['status'] == 'queued' for item in payload)

    notifications_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/notifications",
        headers=user_auth_headers,
    )
    assert notifications_response.status_code == 200
    assert not any(item['type'] == 'match_start' and item['payload_json']['entity_id'] == 2 for item in notifications_response.json()['data'])


async def test_set_finished_event_creates_notification(async_client, user_auth_headers, admin_auth_headers) -> None:
    subscribe_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        headers=user_auth_headers,
        json={
            'entity_type': 'match',
            'entity_id': 2,
            'notification_types': ['set_finished'],
            'channels': ['web'],
        },
    )
    assert subscribe_response.status_code == 200

    event_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/2/events",
        headers=admin_auth_headers,
        json={
            'event_type': 'set_finished',
            'set_number': 3,
            'game_number': 9,
            'player_id': 3,
            'payload_json': {'score': '6-4 4-6 6-3'},
        },
    )
    assert event_response.status_code == 200

    notifications_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/notifications",
        headers=user_auth_headers,
    )
    assert notifications_response.status_code == 200
    assert any(
        item['type'] == 'set_finished'
        and item['payload_json']['entity_id'] == 2
        and item['payload_json']['set_number'] == 3
        for item in notifications_response.json()['data']
    )


async def test_tournament_start_notification_for_subscriber(async_client, user_auth_headers, admin_auth_headers) -> None:
    subscribe_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        headers=user_auth_headers,
        json={
            'entity_type': 'tournament',
            'entity_id': 1,
            'notification_types': ['tournament_start'],
            'channels': ['web'],
        },
    )
    assert subscribe_response.status_code == 200

    update_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tournaments/1",
        headers=admin_auth_headers,
        json={'status': 'live'},
    )
    assert update_response.status_code == 200

    notifications_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/notifications",
        headers=user_auth_headers,
    )
    assert notifications_response.status_code == 200
    assert any(
        item['type'] == 'tournament_start'
        and item['payload_json']['entity_id'] == 1
        for item in notifications_response.json()['data']
    )
