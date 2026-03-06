from fastapi import status

from source.config.settings import settings


async def test_media_and_audit_runtime(async_client, admin_auth_headers) -> None:
    admin_upload = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media/upload",
        json={"filename": "note.txt", "content_type": "text/plain", "content": "binary-image"},
        headers=admin_auth_headers,
    )
    assert admin_upload.status_code == status.HTTP_201_CREATED
    media_id = admin_upload.json()["data"]["id"]

    media_list = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media", headers=admin_auth_headers)
    assert media_list.status_code == status.HTTP_200_OK
    assert any(item["id"] == media_id for item in media_list.json()["data"])

    audit_list = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/audit-logs", headers=admin_auth_headers)
    assert audit_list.status_code == status.HTTP_200_OK
    assert audit_list.json()["data"]

    audit_id = audit_list.json()["data"][0]["id"]
    audit_detail = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/audit-logs/{audit_id}", headers=admin_auth_headers)
    assert audit_detail.status_code == status.HTTP_200_OK

    delete_response = await async_client.delete(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/media/{media_id}", headers=admin_auth_headers)
    assert delete_response.status_code == status.HTTP_200_OK


async def test_public_media_upload_runtime(async_client, admin_auth_headers) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/media/upload",
        files={"file": ("story.txt", b"hello world", "text/plain")},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    media_id = response.json()["data"]["id"]

    get_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/media/{media_id}")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["data"]["filename"] == "story.txt"

    delete_response = await async_client.delete(
        f"{settings.api.prefix}{settings.api.v1.prefix}/media/{media_id}",
        headers=admin_auth_headers,
    )
    assert delete_response.status_code == status.HTTP_200_OK


async def test_integrations_runtime(async_client, admin_auth_headers) -> None:
    patch_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider",
        json={"api_key": "secret", "endpoint": "https://example.invalid"},
        headers=admin_auth_headers,
    )
    assert patch_response.status_code == status.HTTP_200_OK

    sync_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/sync",
        headers=admin_auth_headers,
        json={
            'provider_payload': {
                'events': [
                    {
                        'type': 'score_updated',
                        'timestamp': '2026-03-06T10:00:00Z',
                        'match': {'slug': 'novak-djokovic-vs-jannik-sinner', 'status': 'live', 'tournament_name': 'Australian Open'},
                        'players': [{'name': 'Novak Djokovic'}, {'name': 'Jannik Sinner'}],
                    }
                ]
            }
        },
    )
    assert sync_response.status_code == status.HTTP_200_OK

    list_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations", headers=admin_auth_headers)
    assert list_response.status_code == status.HTTP_200_OK
    assert any(item["provider"] == "live-provider" for item in list_response.json()["data"])

    logs_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/logs", headers=admin_auth_headers)
    assert logs_response.status_code == status.HTTP_200_OK
    assert any("Validated 1 live events from provider payload, applied 0" in item["message"] for item in logs_response.json()["data"])


async def test_integrations_runtime_endpoint_fetch_failure(async_client, admin_auth_headers, monkeypatch) -> None:
    from source.integrations import IntegrationSyncError
    from source.services.operations_service import OperationsService

    class FailingClient:
        async def fetch_events(self, endpoint: str, headers: dict | None = None):
            raise IntegrationSyncError('upstream unavailable')

    monkeypatch.setattr(OperationsService, '_integration_client', lambda self, provider, settings_payload=None: FailingClient())

    await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider",
        json={"endpoint": "https://provider.test/live"},
        headers=admin_auth_headers,
    )

    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/sync",
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_502_BAD_GATEWAY

    logs_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/logs", headers=admin_auth_headers)
    assert any('upstream unavailable' in item['message'] for item in logs_response.json()['data'])


async def test_integrations_runtime_endpoint_fetch_success(async_client, admin_auth_headers, monkeypatch) -> None:
    from source.integrations.provider_contracts import ProviderLiveEvent
    from source.services.operations_service import OperationsService
    from datetime import datetime, UTC

    class SuccessfulClient:
        async def fetch_events(self, endpoint: str, headers: dict | None = None):
            return [
                ProviderLiveEvent(
                    provider='live-provider',
                    event_type='score_updated',
                    match_slug='novak-djokovic-vs-jannik-sinner',
                    tournament_name='Australian Open',
                    player1_name='Novak Djokovic',
                    player2_name='Jannik Sinner',
                    status='live',
                    score_summary='6-4 4-3',
                    occurred_at=datetime.now(tz=UTC),
                    payload={'source': 'endpoint'},
                )
            ]

    monkeypatch.setattr(OperationsService, '_integration_client', lambda self, provider, settings_payload=None: SuccessfulClient())

    await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider",
        json={"endpoint": "https://provider.test/live"},
        headers=admin_auth_headers,
    )

    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/sync",
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    logs_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/logs", headers=admin_auth_headers)
    assert any('Fetched 1 live events from provider endpoint, applied 0' in item['message'] for item in logs_response.json()['data'])

async def test_integration_update_rejects_localhost_endpoint(async_client, admin_auth_headers) -> None:
    response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider",
        json={"endpoint": "http://127.0.0.1:8000/internal"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_integration_update_rejects_embedded_credentials(async_client, admin_auth_headers) -> None:
    response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider",
        json={"endpoint": "https://user:pass@provider.test/live"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_integration_sync_rejects_payload_endpoint_override_to_private_host(async_client, admin_auth_headers) -> None:
    await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider",
        json={"endpoint": "https://provider.test/live"},
        headers=admin_auth_headers,
    )

    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/sync",
        headers=admin_auth_headers,
        json={"endpoint": "http://10.0.0.1/live"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY



async def test_live_integration_sync_updates_existing_match(async_client, admin_auth_headers) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/sync",
        headers=admin_auth_headers,
        json={
            'provider_payload': {
                'events': [
                    {
                        'type': 'set_finished',
                        'timestamp': '2026-03-06T21:15:00Z',
                        'set_number': 3,
                        'game_number': 9,
                        'match': {
                            'slug': 'medvedev-vs-rublev-indian-wells-2026-sf',
                            'status': 'finished',
                            'tournament_name': 'Indian Wells 2026',
                            'score_summary': '6-4 4-6 6-3',
                        },
                        'players': [{'name': 'Daniil Medvedev'}, {'name': 'Andrey Rublev'}],
                    }
                ]
            }
        },
    )
    assert response.status_code == status.HTTP_200_OK

    match_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/matches/2")
    assert match_response.status_code == status.HTTP_200_OK
    match_payload = match_response.json()['data']
    assert match_payload['status'] == 'finished'
    assert match_payload['score_summary'] == '6-4 4-6 6-3'
    assert any(item['event_type'] == 'set_finished' for item in match_payload['timeline'])

    logs_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/logs", headers=admin_auth_headers)
    assert any('Validated 1 live events from provider payload, applied 1' in item['message'] for item in logs_response.json()['data'])


async def test_live_integration_sync_is_idempotent_for_same_provider_event(async_client, admin_auth_headers) -> None:
    payload = {
        'provider_payload': {
            'events': [
                {
                    'type': 'set_finished',
                    'timestamp': '2026-03-06T21:30:00Z',
                    'set_number': 3,
                    'game_number': 9,
                    'match': {
                        'slug': 'medvedev-vs-rublev-indian-wells-2026-sf',
                        'status': 'finished',
                        'tournament_name': 'Indian Wells 2026',
                        'score_summary': '6-4 4-6 6-3',
                    },
                    'players': [{'name': 'Daniil Medvedev'}, {'name': 'Andrey Rublev'}],
                }
            ]
        }
    }

    first = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/sync",
        headers=admin_auth_headers,
        json=payload,
    )
    second = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/sync",
        headers=admin_auth_headers,
        json=payload,
    )
    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK

    timeline_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/matches/2/timeline")
    assert timeline_response.status_code == status.HTTP_200_OK
    matching = [item for item in timeline_response.json()['data'] if item['event_type'] == 'set_finished' and item['payload_json'].get('provider_event_key', '').endswith('2026-03-06T21:30:00+00:00')]
    assert len(matching) == 1


async def test_rankings_integration_endpoint_sync_updates_current_rankings(async_client, admin_auth_headers, monkeypatch) -> None:
    from source.integrations.provider_contracts import ProviderRankingRow
    from source.services.operations_service import OperationsService

    class SuccessfulRankingsClient:
        async def fetch_rankings(self, endpoint: str, headers: dict | None = None):
            return [
                ProviderRankingRow(
                    ranking_type='atp',
                    ranking_date='2026-03-13',
                    position=1,
                    player_name='Jannik Sinner',
                    country_code='IT',
                    points=9400,
                    movement=1,
                ),
                ProviderRankingRow(
                    ranking_type='atp',
                    ranking_date='2026-03-13',
                    position=2,
                    player_name='Novak Djokovic',
                    country_code='RS',
                    points=9000,
                    movement=-1,
                ),
            ]

    monkeypatch.setattr(OperationsService, '_integration_client', lambda self, provider, settings_payload=None: SuccessfulRankingsClient())

    await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/rankings-provider",
        json={"endpoint": "https://provider.test/rankings"},
        headers=admin_auth_headers,
    )

    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/rankings-provider/sync",
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    rankings_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/rankings/current?ranking_type=atp")
    assert rankings_response.status_code == status.HTTP_200_OK
    rows = rankings_response.json()['data']
    assert rows[0]['player_name'] == 'Jannik Sinner'
    assert rows[0]['ranking_date'] == '2026-03-13'

    player_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/players/2")
    assert player_response.status_code == status.HTTP_200_OK
    assert player_response.json()['data']['current_rank'] == 1
    assert player_response.json()['data']['current_points'] == 9400

    logs_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/rankings-provider/logs", headers=admin_auth_headers)
    assert any('Fetched 2 ranking rows from provider endpoint, applied 2' in item['message'] for item in logs_response.json()['data'])


async def test_live_integration_sync_ignores_out_of_order_older_event(async_client, admin_auth_headers) -> None:
    newer_payload = {
        'provider_payload': {
            'events': [
                {
                    'type': 'score_updated',
                    'timestamp': '2026-03-06T21:45:00Z',
                    'match': {
                        'slug': 'medvedev-vs-rublev-indian-wells-2026-sf',
                        'status': 'live',
                        'tournament_name': 'Indian Wells 2026',
                        'score_summary': '6-4 4-6 4-2',
                    },
                    'players': [{'name': 'Daniil Medvedev'}, {'name': 'Andrey Rublev'}],
                }
            ]
        }
    }
    older_payload = {
        'provider_payload': {
            'events': [
                {
                    'type': 'score_updated',
                    'timestamp': '2026-03-06T20:45:00Z',
                    'match': {
                        'slug': 'medvedev-vs-rublev-indian-wells-2026-sf',
                        'status': 'live',
                        'tournament_name': 'Indian Wells 2026',
                        'score_summary': '6-4 4-6 3-1',
                    },
                    'players': [{'name': 'Daniil Medvedev'}, {'name': 'Andrey Rublev'}],
                }
            ]
        }
    }

    first = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/sync",
        headers=admin_auth_headers,
        json=newer_payload,
    )
    second = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/sync",
        headers=admin_auth_headers,
        json=older_payload,
    )
    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK

    match_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/matches/2")
    assert match_response.status_code == status.HTTP_200_OK
    assert match_response.json()['data']['score_summary'] == '6-4 4-6 4-2'

    logs_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider/logs", headers=admin_auth_headers)
    assert any('Validated 1 live events from provider payload, applied 0' in item['message'] for item in logs_response.json()['data'])



async def test_audit_logs_support_filters(async_client, admin_auth_headers) -> None:
    await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users/2/role",
        json={"role": "editor"},
        headers=admin_auth_headers,
    )
    await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/users/2/status",
        json={"status": "inactive"},
        headers=admin_auth_headers,
    )

    action_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/audit-logs",
        params={"action": "admin.user.update"},
        headers=admin_auth_headers,
    )
    assert action_response.status_code == status.HTTP_200_OK
    assert action_response.json()["data"]
    assert all(item["action"] == "admin.user.update" for item in action_response.json()["data"])

    entity_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/audit-logs",
        params={"entity_type": "user", "user_id": 1},
        headers=admin_auth_headers,
    )
    assert entity_response.status_code == status.HTTP_200_OK
    assert entity_response.json()["data"]
    assert all(item["entity_type"] == "user" for item in entity_response.json()["data"])

    today = action_response.json()["data"][0]["created_at"][:10]
    date_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/audit-logs",
        params={"date_from": today, "date_to": today},
        headers=admin_auth_headers,
    )
    assert date_response.status_code == status.HTTP_200_OK
    assert date_response.json()["data"]



async def test_admin_jobs_runtime(async_client, admin_auth_headers) -> None:
    process_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/jobs/process",
        headers=admin_auth_headers,
    )
    assert process_response.status_code == status.HTTP_200_OK

    jobs_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/jobs",
        headers=admin_auth_headers,
    )
    assert jobs_response.status_code == status.HTTP_200_OK
    assert isinstance(jobs_response.json()["data"], list)

    prune_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/jobs/prune",
        headers=admin_auth_headers,
        json={},
    )
    assert prune_response.status_code == status.HTTP_200_OK
    assert "removed" in prune_response.json()["data"]



async def test_admin_maintenance_runtime(async_client, admin_auth_headers) -> None:
    list_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/maintenance",
        headers=admin_auth_headers,
    )
    assert list_response.status_code == status.HTTP_200_OK
    assert any(item["code"] == "search_index" for item in list_response.json()["data"])

    run_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/maintenance/run",
        headers=admin_auth_headers,
        json={"job_type": "rebuild_search_index"},
    )
    assert run_response.status_code == status.HTTP_200_OK
    assert run_response.json()["data"]["job_type"] == "rebuild_search_index"


async def test_admin_integrations_support_filters(async_client, admin_auth_headers) -> None:
    update_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations/live-provider",
        json={"endpoint": "https://example.com/live-feed"},
        headers=admin_auth_headers,
    )
    assert update_response.status_code == status.HTTP_200_OK

    response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/integrations",
        params={"provider": "live", "status": "configured"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert any(item["provider"] == "live-provider" for item in response.json()["data"])


async def test_admin_logs_runtime(async_client, admin_auth_headers) -> None:
    await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/health/ready")
    response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/logs",
        params={"category": "access", "limit": 20},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json()["data"], list)

    app_logs = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/logs",
        params={"category": "application", "limit": 20},
        headers=admin_auth_headers,
    )
    assert app_logs.status_code == status.HTTP_200_OK

    summary = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/logs/summary",
        params={"category": "access", "limit": 20},
        headers=admin_auth_headers,
    )
    assert summary.status_code == status.HTTP_200_OK
    assert "total" in summary.json()["data"]
    assert "categories" in summary.json()["data"]


async def test_admin_maintenance_backups_runtime(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/maintenance/run",
        json={"job_type": "backup_runtime"},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    assert create_response.json()["data"]["job_type"] == "backup_runtime"

    list_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/maintenance/backups",
        headers=admin_auth_headers,
    )
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["data"]

    archive_path = list_response.json()["data"][0]["path"]
    restore_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/maintenance/run",
        json={"job_type": "restore_runtime", "archive_path": archive_path},
        headers=admin_auth_headers,
    )
    assert restore_response.status_code == status.HTTP_200_OK
    assert restore_response.json()["data"]["job_type"] == "restore_runtime"
    assert restore_response.json()["data"]["status"] == "finished"


async def test_admin_jobs_detail_and_cancel_runtime(async_client, admin_auth_headers) -> None:
    from source.services import JobService

    job_service = JobService()
    pending = await job_service.enqueue(job_type='clear_cache', payload={'prefixes': ['matches:']})

    detail_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/jobs/{pending['id']}",
        headers=admin_auth_headers,
    )
    assert detail_response.status_code == status.HTTP_200_OK
    assert detail_response.json()["data"]["job_type"] == 'clear_cache'

    cancel_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/jobs/{pending['id']}/cancel",
        headers=admin_auth_headers,
    )
    assert cancel_response.status_code == status.HTTP_200_OK
    assert cancel_response.json()["data"]["status"] == 'cancelled'
