from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError
from starlette.requests import Request

from source.config.settings import settings
from source.db.models import Match, Player, RankingSnapshot
from source.services.cache_service import CacheService
from source.services.live_hub import LiveHub
from source.services.public_data_service import PublicDataService
from source.services.runtime_state_store import RuntimeStateStore
from source.schemas.pydantic.auth import ResetPasswordRequest, VerifyEmailRequest
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
