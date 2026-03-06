from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from source.config.settings import settings
from source.db.models import Match, Player, RankingSnapshot
from source.services.cache_service import CacheService
from source.services.live_hub import LiveHub
from source.services.public_data_service import PublicDataService
from source.services.runtime_state_store import RuntimeStateStore
from source.services.token_codec import TokenCodec
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
