from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError
from starlette.requests import Request

from source.config.settings import settings
from source.db.models import Match, Player, RankingSnapshot
from source.services.cache_service import CacheService
from source.services.job_service import JobService
from source.services.live_hub import LiveHub
from source.services.public_data_service import PublicDataService
from source.services.runtime_state_store import RuntimeStateStore
from source.schemas.pydantic.auth import ResetPasswordRequest, VerifyEmailRequest
from source.schemas.pydantic.user import UserPasswordChangeRequest
from source.services.token_codec import TokenCodec, token_codec
from source.services.user_engagement_service import UserEngagementService


class FakeWebSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.accepted = False
        self.messages: list[dict] = []
        self.fail_send = fail_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        if self.fail_send:
            raise RuntimeError('socket failed')
        self.messages.append(payload)


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def get(self, key: str):
        return self.storage.get(key)

    def set(self, key: str, value: str) -> None:
        self.storage[key] = value

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        del ttl_seconds
        self.storage[key] = value

    def delete(self, key: str) -> None:
        self.storage.pop(key, None)

    def scan_iter(self, match: str):
        prefix = match.rstrip('*')
        for key in list(self.storage):
            if key.startswith(prefix):
                yield key


@pytest.mark.asyncio
async def test_cache_service_get_or_set_and_bypass(monkeypatch) -> None:
    cache = CacheService()
    calls = {'count': 0}

    async def loader() -> dict[str, str]:
        calls['count'] += 1
        return {'value': 'ok'}

    first = await cache.get_or_set(key='unit:test', schema=dict[str, str], loader=loader, ttl_seconds=60)
    second = await cache.get_or_set(key='unit:test', schema=dict[str, str], loader=loader, ttl_seconds=60)

    assert first == {'value': 'ok'}
    assert second == {'value': 'ok'}
    assert calls['count'] == 1

    monkeypatch.setattr(settings.cache, 'enabled', False)
    third = await cache.get_or_set(key='unit:test:no-cache', schema=dict[str, str], loader=loader, ttl_seconds=60)
    assert third == {'value': 'ok'}
    assert calls['count'] == 2
    monkeypatch.setattr(settings.cache, 'enabled', True)


@pytest.mark.asyncio
async def test_live_hub_connect_subscribe_broadcast_and_cleanup() -> None:
    hub = LiveHub()
    good = FakeWebSocket()
    stale = FakeWebSocket(fail_send=True)

    good_id = await hub.connect(good)
    stale_id = await hub.connect(stale)

    assert good.accepted is True
    assert stale.accepted is True

    assert hub.subscribe(good_id, ['live:all', '']) == ['live:all']
    assert hub.subscribe(stale_id, ['live:all', 'live:match:2']) == ['live:all', 'live:match:2']
    assert hub.unsubscribe(stale_id, ['live:match:2']) == ['live:all']
    assert hub.channels(good_id) == ['live:all']

    await hub.broadcast(channels=['live:all'], payload={'event': 'score_updated'})

    assert good.messages == [{'event': 'score_updated'}]
    assert stale_id not in hub._connections

    hub.disconnect(good_id)
    assert good_id not in hub._connections


def test_runtime_state_store_local_namespace_and_cache_lifecycle() -> None:
    store = RuntimeStateStore()
    store.write_namespace('smoke-local', {'ok': True})
    assert store.read_namespace('smoke-local', {}) == {'ok': True}

    store.set_cache_entry('unit:key', {'expires_at': time.time() + 60, 'payload': {'x': 1}})
    assert store.get_cache_entry('unit:key')['payload'] == {'x': 1}

    store.set_cache_entry('unit:expired', {'expires_at': time.time() - 1, 'payload': {'x': 2}})
    assert store.get_cache_entry('unit:expired') is None

    store.invalidate_cache_prefixes('unit:')
    assert store.get_cache_entry('unit:key') is None

    store.write_namespace('temp-delete', {'value': 1})
    store.delete_namespace('temp-delete')
    assert store.read_namespace('temp-delete', {}) == {}


def test_runtime_state_store_redis_branches(monkeypatch) -> None:
    fake = FakeRedis()
    store = RuntimeStateStore()
    monkeypatch.setattr(store, '_get_redis', lambda: fake)

    store.write_namespace('redis-ns', {'ok': True})
    assert store.read_namespace('redis-ns', {}) == {'ok': True}

    store.set_cache_entry('redis:key', {'expires_at': time.time() + 60, 'payload': {'cached': True}})
    assert store.get_cache_entry('redis:key')['payload'] == {'cached': True}

    store.invalidate_cache_prefixes('redis:')
    assert store.get_cache_entry('redis:key') is None

    store.set_cache_entry('redis:key2', {'expires_at': time.time() + 60, 'payload': {'cached': 2}})
    store.clear_cache()
    assert fake.storage == {
        f"{settings.redis.key_prefix}:state:redis-ns": json.dumps({'ok': True}, ensure_ascii=True, sort_keys=True),
        f"{settings.redis.key_prefix}:state:cache": json.dumps({}, ensure_ascii=True, sort_keys=True),
    }


def test_token_codec_roundtrip_and_error_paths() -> None:
    codec = TokenCodec('unit-secret')
    token = codec.encode({'sub': 1, 'exp': int(time.time()) + 30})
    assert codec.decode(token)['sub'] == 1

    access = codec.issue_access_token(5)
    refresh, refresh_payload = codec.issue_refresh_token(5)
    assert codec.decode(access)['typ'] == 'access'
    assert codec.decode(refresh)['jti'] == refresh_payload['jti']

    with pytest.raises(HTTPException):
        codec.decode('broken-token')

    broken = token + 'tampered'
    with pytest.raises(HTTPException):
        codec.decode(broken)

    expired = codec.encode({'sub': 1, 'exp': int(time.time()) - 1})
    with pytest.raises(HTTPException):
        codec.decode(expired)


def test_public_data_service_helper_methods() -> None:
    service = PublicDataService()
    meta = service._meta(page=2, per_page=20, total=45)
    assert meta.total_pages == 3

    assert service._normalize_search_query('  novak   sinner  ') == 'novak sinner'
    assert service._normalize_search_types(['players', 'matches']) == {'players', 'matches'}

    with pytest.raises(HTTPException):
        service._normalize_search_query('   ')

    with pytest.raises(HTTPException):
        service._normalize_search_types(['players', 'unknown'])

    player1 = Player(id=1, slug='novak-djokovic', first_name='Novak', last_name='Djokovic', full_name='Novak Djokovic', country_code='SRB', country_name='Serbia', status='active')
    player2 = Player(id=2, slug='jannik-sinner', first_name='Jannik', last_name='Sinner', full_name='Jannik Sinner', country_code='ITA', country_name='Italy', status='active')
    match = Match(id=1, slug='novak-vs-sinner', tournament_id=1, round_code='F', best_of_sets=5, player1_id=1, player2_id=2, status='scheduled')
    ranking = RankingSnapshot(id=1, ranking_type='atp', ranking_date='2026-03-06', player_id=1, rank_position=1, points=1000, movement=0)

    assert service._match_score_value(match, {1: player1, 2: player2}) == 'Novak Djokovic vs Jannik Sinner'
    entry = service._ranking_entry(ranking, {1: player1})
    assert entry.player_name == 'Novak Djokovic'

    with pytest.raises(HTTPException):
        service._ranking_entry(ranking, {})


def test_user_engagement_service_validation_helpers() -> None:
    service = UserEngagementService()
    assert service._normalize_unique(['web', 'web', ' email ', '']) == ['web', 'email']
    assert service._validate_subscription_payload(['match_start', 'match_start'], ['web', 'web']) == (['match_start'], ['web'])

    with pytest.raises(HTTPException):
        service._validate_subscription_payload([], ['web'])

    with pytest.raises(HTTPException):
        service._validate_subscription_payload(['match_start'], [])

    with pytest.raises(HTTPException):
        service._validate_subscription_payload(['unsupported'], ['web'])

    with pytest.raises(HTTPException):
        service._validate_subscription_payload(['match_start'], ['pager'])

from datetime import UTC, date, datetime

from source.services import __all__ as services_all
from source.services import AuthUserService, live_hub
from source.services.auth_user_service import _check_password_strength, _hash_password, _verify_password
from source.services.runtime_state_store import RuntimeStateStore
from source.services.token_codec import _b64decode, _b64encode


def _request_scope(*, host: str | None = '127.0.0.1') -> Request:
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': '/',
        'headers': [],
        'query_string': b'',
        'scheme': 'http',
        'server': ('test', 80),
        'http_version': '1.1',
    }
    if host is not None:
        scope['client'] = (host, 12345)
    return Request(scope)


def test_services_module_exports_are_stable() -> None:
    assert 'AuthUserService' in services_all
    assert 'WorkflowService' in services_all
    assert live_hub is not None


def test_cache_service_admin_methods(monkeypatch) -> None:
    cache = CacheService()
    invalidated: list[tuple[str, ...]] = []
    cleared = {'count': 0}
    monkeypatch.setattr(cache.store, 'invalidate_cache_prefixes', lambda *prefixes: invalidated.append(prefixes))
    monkeypatch.setattr(cache.store, 'clear_cache', lambda: cleared.__setitem__('count', cleared['count'] + 1))
    monkeypatch.setattr(cache.store, 'backend_name', lambda: 'local')

    cache.invalidate_prefixes('players:', 'news:')
    assert invalidated == [('players:', 'news:')]

    monkeypatch.setattr(settings.cache, 'enabled', False)
    cache.invalidate_prefixes('ignored:')
    monkeypatch.setattr(settings.cache, 'enabled', True)
    assert invalidated == [('players:', 'news:')]

    cache.clear()
    assert cleared['count'] == 1
    assert cache.backend_name() == 'local'


def test_runtime_state_store_handles_bad_local_json(tmp_path) -> None:
    store = RuntimeStateStore()
    store.base_path = tmp_path / 'state'
    target = store._namespace_path('broken')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{broken')
    assert store.read_namespace('broken', {'fallback': True}) == {'fallback': True}


class BrokenRedis(FakeRedis):
    def get(self, key: str):
        raise RedisError('boom')

    def set(self, key: str, value: str) -> None:
        raise RedisError('boom')

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        raise RedisError('boom')

    def delete(self, key: str) -> None:
        raise RedisError('boom')

    def scan_iter(self, match: str):
        raise RedisError('boom')


def test_runtime_state_store_falls_back_when_redis_fails(monkeypatch, tmp_path) -> None:
    store = RuntimeStateStore()
    store.base_path = tmp_path / 'state'
    monkeypatch.setattr(store, '_get_redis', lambda: BrokenRedis())

    store.write_namespace('ns', {'ok': True})
    assert store.read_namespace('ns', {}) == {'ok': True}

    store.set_cache_entry('key', {'expires_at': time.time() + 60, 'payload': {'x': 1}})
    assert store.get_cache_entry('key')['payload'] == {'x': 1}
    store.invalidate_cache_prefixes('key')
    assert store.get_cache_entry('key') is None


def test_token_codec_helpers_cover_base64_paths() -> None:
    raw = b'tennis-portal'
    assert _b64decode(_b64encode(raw)) == raw


@pytest.mark.asyncio
async def test_auth_user_service_helper_branches(async_client, user_auth_headers) -> None:
    service = AuthUserService()

    hashed = _hash_password('StrongPass123')
    assert _verify_password('StrongPass123', hashed) is True
    assert _verify_password('WrongPass123', hashed) is False
    assert _verify_password('WrongPass123', 'broken') is False

    with pytest.raises(HTTPException):
        _check_password_strength('weak')

    assert service._client_ip(None) == 'unknown'
    assert service._client_ip(_request_scope(host=None)) == 'unknown'
    assert service._client_ip(_request_scope(host='10.0.0.5')) == '10.0.0.5'
    assert service._login_key(_request_scope(host='10.0.0.5'), ' Demo_User ') == '10.0.0.5::demo_user'

    payload = {
        'at': datetime(2026, 3, 6, 12, 0, tzinfo=UTC),
        'day': date(2026, 3, 6),
        'items': [datetime(2026, 3, 6, 13, 0, tzinfo=UTC)],
    }
    json_ready = service._json_ready(payload)
    assert json_ready['at'].startswith('2026-03-06T12:00:00')
    assert json_ready['day'] == '2026-03-06'
    assert json_ready['items'][0].startswith('2026-03-06T13:00:00')

    with pytest.raises(HTTPException):
        await service.reset_password(ResetPasswordRequest(token=' ', new_password='StrongPass123'))

    with pytest.raises(HTTPException):
        await service.verify_email(VerifyEmailRequest(token=' '))

    with pytest.raises(HTTPException):
        service._consume_action_token('bad-token', purpose='password_reset')

    action_token = service._issue_action_token(user_id=2, purpose='verify_email', ttl_minutes=5)
    consumed = service._consume_action_token(action_token, purpose='verify_email')
    assert consumed['sub'] == 2
    with pytest.raises(HTTPException):
        service._consume_action_token(action_token, purpose='verify_email')

    wrong_type_token = token_codec.encode({'sub': 2, 'typ': 'access', 'exp': int(time.time()) + 30})
    with pytest.raises(HTTPException):
        service._consume_refresh_token(wrong_type_token, revoke_only=False)

    refresh, refresh_payload = token_codec.issue_refresh_token(2)
    service.store.write_namespace(service.refresh_namespace, {
        refresh_payload['jti']: {'user_id': 2, 'expires_at': refresh_payload['exp'], 'revoked': True}
    })
    with pytest.raises(HTTPException):
        service._consume_refresh_token(refresh, revoke_only=False)

    auth_me = await async_client.get('/api/v1/auth/me', headers=user_auth_headers)
    assert auth_me.status_code == 200

from source.integrations import IntegrationSyncError, LiveScoreProviderClient, RankingsProviderClient
from source.services.operations_service import OperationsService


def test_operations_service_json_and_media_helpers(tmp_path) -> None:
    service = OperationsService()
    service.storage_dir = tmp_path
    service.media_dir = tmp_path / 'media'
    service.media_index_file = tmp_path / 'media_index.json'
    service.integrations_file = tmp_path / 'integrations.json'

    service._ensure_storage()
    assert service.media_dir.exists()

    assert service._read_json(tmp_path / 'missing.json', {'ok': True}) == {'ok': True}
    service._write_json(tmp_path / 'payload.json', {'value': 1})
    assert service._read_json(tmp_path / 'payload.json', {}) == {'value': 1}

    service._save_media_records([{'id': 1, 'filename': 'note.txt', 'content_type': 'text/plain', 'url': '/media/note.txt'}])
    assert service._media_records()[0]['filename'] == 'note.txt'
    assert service._media_item({'id': 1, 'filename': 'note.txt', 'content_type': 'text/plain', 'url': '/media/note.txt', 'size': 4}).filename == 'note.txt'
    assert service._sanitize_filename('../ unsafe name!!.txt') == 'unsafe_name_.txt'


def test_operations_service_upload_validation_and_signatures() -> None:
    service = OperationsService()

    service._validate_upload('note.txt', 'text/plain', 4)

    with pytest.raises(HTTPException):
        service._validate_upload('../note.txt', 'text/plain', 4)
    with pytest.raises(HTTPException):
        service._validate_upload('note.exe', 'text/plain', 4)
    with pytest.raises(HTTPException):
        service._validate_upload('note.txt', 'application/octet-stream', 4)
    with pytest.raises(HTTPException):
        service._validate_upload('note.txt', 'text/plain', settings.media.max_upload_size_bytes + 1)

    service._validate_content_signature('text/plain', b'hello')
    service._validate_content_signature('image/png', b'\x89PNG\r\n\x1a\nrest')
    service._validate_content_signature('image/gif', b'GIF89a rest')
    service._validate_content_signature('image/webp', b'RIFF1234WEBPmore')
    service._validate_content_signature('image/jpeg', b'\xff\xd8\xffbody\xff\xd9')

    for content_type, payload in [
        ('text/plain', b'hello\x00world'),
        ('image/png', b'bad'),
        ('image/gif', b'bad'),
        ('image/webp', b'bad'),
        ('image/jpeg', b'bad'),
    ]:
        with pytest.raises(HTTPException):
            service._validate_content_signature(content_type, payload)


def test_operations_service_decoders_and_integration_helpers(monkeypatch) -> None:
    service = OperationsService()

    assert service._decode_media_content({'content': 'hello'}) == b'hello'
    assert service._decode_media_content({'content': b'hello'}) == b'hello'
    assert service._decode_media_content({'content_base64': base64.b64encode(b'hello').decode()}) == b'hello'
    with pytest.raises(HTTPException):
        service._decode_media_content({'content_base64': '%%%bad'})

    assert service._validate_integration_endpoint('https://provider.test/live') == 'https://provider.test/live'
    assert service._validate_integration_endpoint('') == ''
    for endpoint in [
        'ftp://provider.test/live',
        'https://user:pass@provider.test/live',
        'http://localhost/live',
        'http://127.0.0.1/live',
    ]:
        with pytest.raises(HTTPException):
            service._validate_integration_endpoint(endpoint)

    normalized = service._normalize_integration_settings({
        'endpoint': 'https://provider.test/live',
        'headers': {'Authorization': 'Bearer token'},
        'timeout_seconds': 3,
        'max_attempts': 2,
        'enabled': True,
        'empty': '',
    })
    assert normalized['headers']['Authorization'] == 'Bearer token'
    assert normalized['timeout_seconds'] == 3.0
    assert normalized['max_attempts'] == 2
    assert normalized['enabled'] is True
    assert 'empty' not in normalized

    with pytest.raises(HTTPException):
        service._normalize_integration_settings({'headers': 'bad'})
    with pytest.raises(HTTPException):
        service._normalize_integration_settings({'timeout_seconds': 0})
    with pytest.raises(HTTPException):
        service._normalize_integration_settings({'max_attempts': 0})

    assert isinstance(service._integration_client('live-provider', {'timeout_seconds': 1, 'max_attempts': 1}), LiveScoreProviderClient)
    assert isinstance(service._integration_client('rankings-provider', {'timeout_seconds': 1, 'max_attempts': 1}), RankingsProviderClient)
    assert service._integration_client('other-provider', {}) is None


@pytest.mark.asyncio
async def test_operations_service_list_integrations_reads_file_store(tmp_path) -> None:
    service = OperationsService()
    service.storage_dir = tmp_path
    service.media_dir = tmp_path / 'media'
    service.media_index_file = tmp_path / 'media_index.json'
    service.integrations_file = tmp_path / 'integrations.json'
    service._save_integration_records({
        'live-provider': {
            'status': 'ok',
            'last_sync_at': '2026-03-06T12:00:00+00:00',
            'last_error': None,
            'settings': {},
            'logs': [{'timestamp': '2026-03-06T12:00:00+00:00', 'message': 'sync ok'}],
        }
    })

    payload = await service.list_integrations()
    assert payload.data[0].provider == 'live-provider'
    assert payload.data[0].status == 'ok'

    logs = await service.get_integration_logs('live-provider')
    assert logs.data[0].message == 'sync ok'
    assert logs.data[0].level == 'info'

    with pytest.raises(HTTPException):
        await service.get_integration_logs('missing-provider')


def test_cache_service_disabled_and_clear_branch(monkeypatch) -> None:
    cache = CacheService()
    cleared = {'count': 0}
    monkeypatch.setattr(cache.store, 'clear_cache', lambda: cleared.__setitem__('count', cleared['count'] + 1))
    monkeypatch.setattr(settings.cache, 'enabled', False)
    cache.invalidate_prefixes('players:')
    cache.clear()
    monkeypatch.setattr(settings.cache, 'enabled', True)
    assert cleared['count'] == 1


def test_token_codec_additional_error_branches() -> None:
    codec = TokenCodec('unit-secret')

    with pytest.raises(HTTPException):
        codec.decode('missingdot')

    expired = codec.encode({'sub': 1, 'exp': int(time.time()) - 10})
    with pytest.raises(HTTPException):
        codec.decode(expired)


@pytest.mark.asyncio
async def test_job_service_branch_coverage(monkeypatch) -> None:
    jobs = JobService()

    monkeypatch.setattr(settings.jobs, 'enabled', False)
    assert await jobs.process_due_jobs() == 0
    monkeypatch.setattr(settings.jobs, 'enabled', True)

    fake_jobs = [
        {
            'id': 1,
            'job_type': 'generate_sitemap',
            'status': 'finished',
            'payload': {},
            'run_at': datetime.now(tz=UTC).isoformat(),
            'created_at': datetime.now(tz=UTC).isoformat(),
            'updated_at': datetime.now(tz=UTC).isoformat(),
            'attempts': 1,
            'error': None,
        },
        {
            'id': 2,
            'job_type': 'generate_sitemap',
            'status': 'pending',
            'payload': {},
            'run_at': datetime(2999, 1, 1, tzinfo=UTC).isoformat(),
            'created_at': datetime.now(tz=UTC).isoformat(),
            'updated_at': datetime.now(tz=UTC).isoformat(),
            'attempts': 0,
            'error': None,
        },
        {
            'id': 3,
            'job_type': 'unsupported',
            'status': 'pending',
            'payload': {},
            'run_at': datetime.now(tz=UTC).isoformat(),
            'created_at': datetime.now(tz=UTC).isoformat(),
            'updated_at': datetime.now(tz=UTC).isoformat(),
            'attempts': 0,
            'error': None,
        },
    ]
    monkeypatch.setattr(jobs, '_read_jobs', lambda: fake_jobs)
    written = {}
    monkeypatch.setattr(jobs, '_write_jobs', lambda payload: written.setdefault('jobs', payload))
    monkeypatch.setattr(jobs.workflows, 'generate_sitemap_snapshot', AsyncMock())

    processed = await jobs.process_due_jobs()
    assert processed == 0
    assert written['jobs'][2]['status'] == 'failed'
    assert 'Unsupported job type' in written['jobs'][2]['error']

    invalidated = {'prefixes': None, 'cleared': 0}
    monkeypatch.setattr(jobs.cache, 'invalidate_prefixes', lambda *prefixes: invalidated.__setitem__('prefixes', prefixes))
    monkeypatch.setattr(jobs.cache, 'clear', lambda: invalidated.__setitem__('cleared', invalidated['cleared'] + 1))
    monkeypatch.setattr(jobs.workflows, 'process_finalized_match', AsyncMock())
    monkeypatch.setattr(jobs.workflows, 'publish_due_scheduled_news', AsyncMock())
    monkeypatch.setattr(jobs.workflows, 'generate_sitemap_snapshot', AsyncMock())
    monkeypatch.setattr(jobs.workflows, 'rebuild_search_index', AsyncMock())
    monkeypatch.setattr(jobs.workflows, 'recalculate_player_aggregates', AsyncMock())
    monkeypatch.setattr(jobs.workflows, 'recalculate_h2h', AsyncMock())
    monkeypatch.setattr(jobs.admin_support, 'import_rankings', AsyncMock())
    monkeypatch.setattr(jobs.operations, 'sync_integration', AsyncMock())

    await jobs._run_job('clear_cache', {'prefixes': ['players:', 'news:']})
    assert invalidated['prefixes'] == ('players:', 'news:')

    await jobs._run_job('clear_cache', {})
    assert invalidated['cleared'] == 1

    await jobs._run_job('finalize_match_postprocess', {'match_id': 2})
    jobs.workflows.process_finalized_match.assert_awaited_with(2)

    await jobs._run_job('publish_scheduled_news', {'news_id': 5})
    jobs.workflows.publish_due_scheduled_news.assert_awaited_with(5)

    await jobs._run_job('generate_sitemap', {'base_url': 'https://example.test'})
    jobs.workflows.generate_sitemap_snapshot.assert_awaited_with('https://example.test')

    await jobs._run_job('rebuild_search_index', {})
    jobs.workflows.rebuild_search_index.assert_awaited()

    await jobs._run_job('recalculate_player_stats', {'player_ids': [1, 2]})
    jobs.workflows.recalculate_player_aggregates.assert_awaited_with([1, 2])

    await jobs._run_job('recalculate_h2h', {'match_id': 2})
    jobs.workflows.recalculate_h2h.assert_awaited_with(2)

    await jobs._run_job('import_rankings', {'source_file': 'rankings.csv'})
    jobs.admin_support.import_rankings.assert_awaited_with({'source_file': 'rankings.csv'})

    await jobs._run_job('sync_live', {'provider': 'live-provider'})
    jobs.operations.sync_integration.assert_awaited_with('live-provider', {'provider': 'live-provider'})

    listed = jobs.list_jobs()
    assert isinstance(listed, list)

    monkeypatch.setattr(jobs, '_read_jobs', lambda: [{'id': 9, 'status': 'failed', 'error': 'boom'}])
    written_retry = {}
    monkeypatch.setattr(jobs, '_write_jobs', lambda payload: written_retry.setdefault('payload', payload))
    monkeypatch.setattr(jobs, 'process_due_jobs', AsyncMock(return_value=1))
    retried = await jobs.retry_failed_job(9)
    assert retried['status'] == 'failed' or retried['status'] == 'pending'

    monkeypatch.setattr(jobs, '_read_jobs', lambda: [{'id': 1, 'status': 'finished'}, {'id': 2, 'status': 'pending'}, {'id': 3, 'status': 'failed'}])
    written_prune = {}
    monkeypatch.setattr(jobs, '_write_jobs', lambda payload: written_prune.setdefault('payload', payload))
    removed = jobs.prune_jobs()
    assert removed == 2
    assert written_prune['payload'] == [{'id': 2, 'status': 'pending'}]

    assert jobs.backend_name() in {'local', 'redis'}

from source.schemas.pydantic.auth import LoginRequest, LogoutRequest, RefreshTokenRequest, RegisterRequest
from source.services.admin_support_service import AdminSupportService


@pytest.mark.asyncio
async def test_admin_support_service_branch_helpers(prepared_test_db: str, monkeypatch, tmp_path) -> None:
    del prepared_test_db
    service = AdminSupportService()
    service.storage_dir = tmp_path
    service.settings_file = tmp_path / 'admin_settings.json'
    service.jobs_file = tmp_path / 'ranking_import_jobs.json'

    with pytest.raises(HTTPException):
        service._require({}, 'slug')

    assert service._read_json(tmp_path / 'missing.json') is None
    service._write_json(service.settings_file, {'seo_title': 'Portal'})
    assert service._read_json(service.settings_file)['seo_title'] == 'Portal'

    invalidated: list[tuple[str, ...]] = []
    monkeypatch.setattr(service.cache, 'invalidate_prefixes', lambda *prefixes: invalidated.append(prefixes))

    settings_payload = await service.update_settings({'seo_title': 'Portal', 'empty': ''})
    assert settings_payload.data['seo_title'] == 'Portal'
    assert invalidated

    list_jobs = await service.list_ranking_jobs()
    assert isinstance(list_jobs.data, list)

    monkeypatch.setattr(service.repo, 'get_first_active_user', AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        await service.send_test_notification()

    with pytest.raises(HTTPException):
        await service.update_category(999, {'name': 'Name', 'slug': 'slug'})
    with pytest.raises(HTTPException):
        await service.delete_category(999)
    with pytest.raises(HTTPException):
        await service.update_tag(999, {'name': 'Name', 'slug': 'slug'})
    with pytest.raises(HTTPException):
        await service.delete_tag(999)

    queued = await service.import_rankings({'source_file': 'rankings.csv'})
    assert queued.data.message == 'Ranking import queued'
    assert service.jobs_file.exists()

    recalculated = await service.recalculate_ranking_movements()
    assert recalculated.data.message == 'Ranking movements recalculated'


@pytest.mark.asyncio
async def test_admin_support_rankings_import_missing_players(prepared_test_db: str, tmp_path) -> None:
    del prepared_test_db
    service = AdminSupportService()
    service.storage_dir = tmp_path
    service.jobs_file = tmp_path / 'ranking_import_jobs.json'

    with pytest.raises(HTTPException):
        await service.import_rankings(
            {
                'provider': 'rankings-provider',
                'provider_payload': {
                    'ranking_type': 'atp',
                    'ranking_date': '2026-03-12',
                    'entries': [
                        {'position': 1, 'player_name': 'Unknown Player', 'country_code': 'US', 'points': 1000},
                    ],
                },
            }
        )


@pytest.mark.asyncio
async def test_auth_user_service_error_branches(prepared_test_db: str, async_client, monkeypatch) -> None:
    del prepared_test_db
    service = AuthUserService()

    with pytest.raises(HTTPException):
        await service.register(None, RegisterRequest(email='admin@makhachkalaopen.ru', username='new_user', password='StrongPass123', privacy_consent=True))

    with pytest.raises(HTTPException):
        await service.register(None, RegisterRequest(email='new@example.com', username='admin', password='StrongPass123', privacy_consent=True))

    inactive_user = SimpleNamespace(id=999, status='inactive')
    monkeypatch.setattr(service.users, 'get', AsyncMock(return_value=inactive_user))
    refresh_token, _ = token_codec.issue_refresh_token(999)
    with pytest.raises(HTTPException):
        await service.refresh(None, RefreshTokenRequest(refresh_token=refresh_token))

    valid_refresh, refresh_payload = token_codec.issue_refresh_token(2)
    service.store.write_namespace(service.refresh_namespace, {
        refresh_payload['jti']: {'user_id': 2, 'expires_at': refresh_payload['exp'], 'revoked': False}
    })
    logout = await service.logout(None, LogoutRequest(refresh_token=valid_refresh))
    assert logout.data.message == 'Logged out'

    invalid_login = await async_client.post('/api/v1/auth/login', json={'email_or_username': 'demo_user', 'password': 'wrong-pass'})
    assert invalid_login.status_code == 401

    login_response = await async_client.post('/api/v1/auth/login', json={'email_or_username': 'demo_user', 'password': 'UserPass123'})
    token = login_response.json()['data']['access_token']
    wrong_password_request = Request({
        'type': 'http',
        'method': 'GET',
        'path': '/',
        'headers': [(b'authorization', f'Bearer {token}'.encode())],
        'query_string': b'',
        'scheme': 'http',
        'server': ('test', 80),
        'client': ('127.0.0.1', 12345),
        'http_version': '1.1',
    })
    with pytest.raises(HTTPException):
        await service.change_password(wrong_password_request, UserPasswordChangeRequest(current_password='bad-current', new_password='UserPass999'))

    service2 = AuthUserService()
    with pytest.raises(HTTPException):
        await service2.get_admin_user(999)
