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


async def test_public_media_upload_runtime(async_client) -> None:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/media/upload",
        files={"file": ("story.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == status.HTTP_201_CREATED
    media_id = response.json()["data"]["id"]

    get_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/media/{media_id}")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["data"]["filename"] == "story.txt"


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
    assert "Validated 1 live events from provider payload, applied 0" in logs_response.json()["data"]["message"]


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
    assert 'upstream unavailable' in logs_response.json()['data']['message']


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
    assert 'Fetched 1 live events from provider endpoint, applied 0' in logs_response.json()['data']['message']

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
    assert 'Validated 1 live events from provider payload, applied 1' in logs_response.json()['data']['message']


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
    assert 'Fetched 2 ranking rows from provider endpoint, applied 2' in logs_response.json()['data']['message']
