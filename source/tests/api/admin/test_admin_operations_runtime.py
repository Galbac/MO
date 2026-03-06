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
    assert "Validated 1 live events from provider payload" in logs_response.json()["data"]["message"]


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
    assert 'Fetched 1 live events from provider endpoint' in logs_response.json()['data']['message']

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

