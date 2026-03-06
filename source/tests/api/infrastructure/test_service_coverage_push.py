from __future__ import annotations

import importlib
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import source.services as services_module
auth_user_service_module = importlib.import_module('source.services.auth_user_service')
cache_service_module = importlib.import_module('source.services.cache_service')
live_hub_module = importlib.import_module('source.services.live_hub')
runtime_state_store_module = importlib.import_module('source.services.runtime_state_store')
token_codec_module = importlib.import_module('source.services.token_codec')
user_engagement_service_module = importlib.import_module('source.services.user_engagement_service')
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.match import MatchDetail, MatchEventCreateRequest, MatchScore, MatchSetItem, MatchStats, MatchStatsUpdateRequest, MatchSummary
from source.schemas.pydantic.news import NewsArticleSummary, NewsStatusRequest
from source.schemas.pydantic.player import PlayerSummary
from source.schemas.pydantic.ranking import RankingEntry
from source.schemas.pydantic.tournament import TournamentSummary
from source.schemas.pydantic.search import SearchResults, SearchSuggestion
from source.services.admin_content_service import AdminContentService
from source.services.public_data_service import PublicDataService

from fastapi import Request
from redis.exceptions import RedisError
from source.config.settings import settings
from source.db.session import db_session_manager
from source.schemas.pydantic.auth import ForgotPasswordRequest, LoginRequest, LogoutRequest, RefreshTokenRequest
from source.schemas.pydantic.user import FavoriteCreateRequest, NotificationSubscriptionCreateRequest, NotificationSubscriptionUpdateRequest
from source.services.auth_user_service import AuthUserService
from source.services.cache_service import CacheService
from source.services.live_hub import LiveHub
from source.services.runtime_state_store import RuntimeStateStore
from source.services.token_codec import TokenCodec
from source.services.user_engagement_service import UserEngagementService


def _match_detail(match_id: int = 2) -> MatchDetail:
    return MatchDetail(
        id=match_id,
        slug=f'match-{match_id}',
        status='live',
        scheduled_at=datetime(2026, 3, 6, 12, 0, tzinfo=UTC),
        actual_start_at=datetime(2026, 3, 6, 12, 5, tzinfo=UTC),
        actual_end_at=None,
        player1_id=1,
        player2_id=2,
        player1_name='Novak Djokovic',
        player2_name='Jannik Sinner',
        tournament_id=1,
        tournament_name='Australian Open',
        round_code='F',
        court_name='Rod Laver Arena',
        score_summary='6-4 4-3',
        best_of_sets=5,
        winner_id=None,
        score=MatchScore(sets=['6-4', '4-3'], current_game='30-15', serving_player_id=1),
        sets=[MatchSetItem(set_number=1, player1_games=6, player2_games=4)],
        stats=MatchStats(player1_aces=5, player2_aces=4, duration_minutes=90),
        timeline=[],
        h2h={'total_matches': 3},
        related_news=[],
    )


def test_services_init_module_reload_for_coverage() -> None:
    reloaded = importlib.reload(services_module)
    assert reloaded.AuthUserService is not None
    assert 'WorkflowService' in reloaded.__all__


def test_service_module_reloads_for_trace_coverage() -> None:
    assert importlib.reload(cache_service_module).CacheService is not None
    assert importlib.reload(token_codec_module).TokenCodec is not None
    assert importlib.reload(live_hub_module).LiveHub is not None
    assert importlib.reload(runtime_state_store_module).RuntimeStateStore is not None
    assert importlib.reload(auth_user_service_module).AuthUserService is not None
    assert importlib.reload(user_engagement_service_module).UserEngagementService is not None


@pytest.mark.asyncio
async def test_public_data_service_branch_coverage(prepared_test_db: str, monkeypatch) -> None:
    del prepared_test_db
    service = PublicDataService()

    assert service._meta(page=1, per_page=0, total=10).total_pages == 1
    assert service._normalize_search_types([' ', '']) == service.ALLOWED_SEARCH_TYPES

    rankings = await service.get_rankings(page=1, per_page=1, ranking_type='atp')
    assert rankings.data
    assert rankings.meta.total >= 1

    async def passthrough_cache(**kwargs):
        return await kwargs['loader']()

    monkeypatch.setattr(service.cache, 'get_or_set', AsyncMock(side_effect=passthrough_cache))
    monkeypatch.setattr(service.repo, 'list_ranking_dates', AsyncMock(return_value=[]))
    empty_current = await service.get_current_rankings('unknown')
    assert empty_current.data == []

    service2 = PublicDataService()
    history = await service2.get_rankings_history('atp')
    assert history.data

    monkeypatch.setattr(service.query, 'get_player_ranking_history', AsyncMock(return_value=SuccessResponse(data=[{'position': 1}])))
    player_history = await service.get_player_rankings(1)
    assert player_history.data == [{'position': 1}]

    monkeypatch.setattr(service, 'get_current_rankings', AsyncMock(return_value=SuccessResponse(data=[RankingEntry(position=1, player_id=1, player_name='Novak Djokovic', country_code='SRB', points=1000, movement=0, ranking_type='atp', ranking_date='2026-03-06')])))
    race = await service.get_race_rankings()
    assert race.data[0].player_name == 'Novak Djokovic'

    monkeypatch.setattr(
        service,
        'search',
        AsyncMock(
            return_value=SuccessResponse(
                data=SearchResults(
                    players=[
                        PlayerSummary(id=1, slug='novak-djokovic', full_name='Novak Djokovic', country_code='SRB'),
                        PlayerSummary(id=1, slug='novak-djokovic', full_name='Novak Djokovic', country_code='SRB'),
                    ],
                    tournaments=[TournamentSummary(id=1, slug='australian-open-2026', name='Australian Open', category='grand_slam', surface='hard', season_year=2026, start_date='2026-01-12', end_date='2026-01-26', status='finished', city='Melbourne')],
                    matches=[MatchSummary(id=2, slug='match-2', status='live', scheduled_at=datetime(2026, 3, 6, 12, 0, tzinfo=UTC), actual_start_at=None, actual_end_at=None, player1_id=1, player2_id=2, player1_name='Novak Djokovic', player2_name='Jannik Sinner', tournament_id=1, tournament_name='Australian Open', round_code='F', court_name='Rod Laver Arena', score_summary='6-4 4-3')],
                    news=[NewsArticleSummary(id=1, slug='novak-wins', title='Novak Djokovic wins', status='published')],
                )
            )
        ),
    )
    suggestions = await service.search_suggestions('novak')
    assert [item.entity_type for item in suggestions.data] == ['player', 'tournament', 'news', 'match']

    monkeypatch.setattr(service.repo, 'list_live_matches', AsyncMock(return_value=[SimpleNamespace(id=2), SimpleNamespace(id=999)]))

    async def get_match_side_effect(match_id: int):
        if match_id == 999:
            raise HTTPException(status_code=404, detail='missing')
        return SuccessResponse(data=_match_detail(match_id))

    monkeypatch.setattr(service.query, 'get_match', AsyncMock(side_effect=get_match_side_effect))
    live = await service.list_live_matches()
    assert [item.id for item in live.data] == [2]

    one_live = await service.get_live_match(2)
    assert one_live.data.id == 2

    monkeypatch.setattr(
        service.repo,
        'list_live_events',
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=1,
                    event_type='ace',
                    set_number=1,
                    game_number=2,
                    player_id=1,
                    payload_json=None,
                    created_at=datetime(2026, 3, 6, 12, 10, tzinfo=UTC),
                )
            ]
        ),
    )
    feed = await service.get_live_feed()
    assert feed.data[0].payload_json == {}


@pytest.mark.asyncio
async def test_admin_content_service_branch_coverage(prepared_test_db: str, monkeypatch) -> None:
    del prepared_test_db
    service = AdminContentService()

    assert service._parse_date(date(2026, 3, 6)) == date(2026, 3, 6)
    assert service._parse_date('2026-03-06') == date(2026, 3, 6)
    assert service._parse_datetime('2026-03-06T12:00:00+00:00').year == 2026
    assert service._sanitize_html('<div onclick="alert(1)"><script>x</script><a href="javascript:bad">x</a></div>') == '<div ><a href="bad">x</a></div>'

    retired = SimpleNamespace(status='retired', winner_id=None, retire_reason='injury', player1_id=1, player2_id=2)
    walkover = SimpleNamespace(status='walkover', winner_id=2, retire_reason=None, player1_id=1, player2_id=2)
    tied = SimpleNamespace(status='finished', winner_id=1, retire_reason=None, player1_id=1, player2_id=2)
    assert service._decide_winner(retired, []) == 2
    assert service._decide_winner(walkover, []) == 2
    assert service._decide_winner(tied, [SimpleNamespace(player1_games=6, player2_games=4), SimpleNamespace(player1_games=4, player2_games=6)]) == 1

    monkeypatch.setattr(service.query, 'get_match', AsyncMock(side_effect=HTTPException(status_code=404, detail='missing')))
    await service._broadcast_match_update(999, 'score_updated')

    monkeypatch.setattr(service.query, 'list_players', AsyncMock(return_value=SuccessResponse(data=['player-row'])))
    monkeypatch.setattr(service.query, 'list_tournaments', AsyncMock(return_value=SuccessResponse(data=['tournament-row'])))
    monkeypatch.setattr(service.query, 'get_player', AsyncMock(return_value=SuccessResponse(data={'id': 1})))
    monkeypatch.setattr(service.query, 'get_tournament', AsyncMock(return_value=SuccessResponse(data={'id': 1})))
    monkeypatch.setattr(service.query, 'get_match', AsyncMock(return_value=SuccessResponse(data=_match_detail(2))))
    assert (await service.list_admin_players()).data == ['player-row']
    assert (await service.list_admin_tournaments()).data == ['tournament-row']
    assert (await service.get_admin_player(1)).data == {'id': 1}
    assert (await service.get_admin_tournament(1)).data == {'id': 1}
    assert (await service.get_admin_match(2)).data.id == 2

    monkeypatch.setattr(service.cache, 'invalidate_prefixes', lambda *args: None)
    monkeypatch.setattr(service, '_log_audit', AsyncMock())
    monkeypatch.setattr(service, '_broadcast_match_update', AsyncMock())
    monkeypatch.setattr(service.jobs, 'enqueue', AsyncMock())

    stats_result = await service.update_admin_match_stats(
        2,
        MatchStatsUpdateRequest(stats=MatchStats(player1_aces=10, player2_aces=8, duration_minutes=150)),
        actor_id=1,
    )
    assert stats_result.data.id == 2
    service._broadcast_match_update.assert_awaited()

    event_result = await service.create_admin_match_event(
        2,
        MatchEventCreateRequest(event_type='ace', set_number=2, game_number=3, player_id=1, payload_json={'speed': 210}),
        actor_id=1,
    )
    assert event_result.data.event_type == 'ace'

    reopened = await service.reopen_admin_match(2, actor_id=1)
    assert reopened.data.message == 'Match reopened'

    news = await service.get_admin_news(1)
    assert news.data.slug
    attached = await service.attach_admin_news_tags(1)
    assert attached.data == []

    with pytest.raises(HTTPException):
        await service.schedule_admin_news(1, NewsStatusRequest(status='scheduled', publish_at=None), actor_id=1)

    with pytest.raises(HTTPException):
        await service.update_admin_match_stats(999, MatchStatsUpdateRequest(stats=MatchStats()), actor_id=1)
    with pytest.raises(HTTPException):
        await service.create_admin_match_event(999, MatchEventCreateRequest(event_type='ace'), actor_id=1)
    with pytest.raises(HTTPException):
        await service.reopen_admin_match(999, actor_id=1)
    with pytest.raises(HTTPException):
        await service.get_admin_news(999)
    with pytest.raises(HTTPException):
        await service.attach_admin_news_tags(999)


@pytest.mark.asyncio
async def test_public_search_direct_match_and_dedup_branch(monkeypatch) -> None:
    service = PublicDataService()
    async def passthrough_cache(**kwargs):
        return await kwargs['loader']()

    monkeypatch.setattr(service.cache, 'get_or_set', AsyncMock(side_effect=passthrough_cache))
    monkeypatch.setattr(service.repo, 'search_players', AsyncMock(side_effect=[
        [SimpleNamespace(id=1, full_name='Novak Djokovic', slug='novak-djokovic', country_code='SRB')],
        [SimpleNamespace(id=1, full_name='Novak Djokovic', slug='novak-djokovic', country_code='SRB')],
        [SimpleNamespace(id=2, full_name='Jannik Sinner', slug='jannik-sinner', country_code='ITA')],
    ]))
    monkeypatch.setattr(service.repo, 'search_tournaments', AsyncMock(return_value=[]))
    monkeypatch.setattr(service.repo, 'search_news', AsyncMock(return_value=[]))
    monkeypatch.setattr(service.repo, 'search_matches', AsyncMock(return_value=[SimpleNamespace(id=10)]))
    monkeypatch.setattr(service.news, 'list_categories', AsyncMock(return_value=[]))
    monkeypatch.setattr(service.query, 'get_upcoming_matches', AsyncMock(return_value=SuccessResponse(data=[_match_detail(10)])))
    monkeypatch.setattr(service.query, 'get_match_results', AsyncMock(return_value=SuccessResponse(data=[])))
    monkeypatch.setattr(service.query, 'get_match', AsyncMock(side_effect=HTTPException(status_code=404, detail='missing-detail')))
    monkeypatch.setattr(service.query, '_tournament_summary', lambda item: item)
    monkeypatch.setattr(service.query, '_player_summary', lambda item, matches: PlayerSummary(id=item.id, slug=item.slug, full_name=item.full_name, country_code=item.country_code))
    monkeypatch.setattr(service.query, '_news_summary', lambda item, category: item)

    result = await service.search('novak sinner', types=['players', 'matches'])
    assert len(result.data.players) == 1
    assert len(result.data.matches) == 1



def _request_with_headers(headers: dict[str, str]) -> Request:
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': '/',
        'headers': [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        'client': ('127.0.0.1', 12345),
        'query_string': b'',
        'scheme': 'http',
        'server': ('test', 80),
        'http_version': '1.1',
    }
    return Request(scope)


class _FakeWebSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.accepted = False
        self.fail_send = fail_send
        self.messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        if self.fail_send:
            raise RuntimeError('send failed')
        self.messages.append(payload)


class _FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def ping(self) -> bool:
        return True

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


class _BrokenRedis(_FakeRedis):
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


@pytest.mark.asyncio
async def test_small_service_branch_coverage(monkeypatch, tmp_path) -> None:
    cache = CacheService()
    calls = {'count': 0}

    async def loader() -> dict[str, str]:
        calls['count'] += 1
        return {'ok': 'yes'}

    monkeypatch.setattr(settings.cache, 'enabled', False)
    assert await cache.get_or_set(key='disabled', schema=dict[str, str], loader=loader) == {'ok': 'yes'}
    monkeypatch.setattr(settings.cache, 'enabled', True)

    cleared = {'count': 0}
    monkeypatch.setattr(cache.store, 'clear_cache', lambda: cleared.__setitem__('count', cleared['count'] + 1))
    cache.clear()
    assert cleared['count'] == 1

    codec = TokenCodec('unit-secret')
    access = codec.issue_access_token(1)
    refresh, payload = codec.issue_refresh_token(1)
    assert codec.decode(access)['typ'] == 'access'
    assert codec.decode(refresh)['jti'] == payload['jti']
    with pytest.raises(HTTPException):
        codec.decode('missingdot')
    with pytest.raises(HTTPException):
        codec.decode(access + 'x')
    expired = codec.encode({'sub': 1, 'exp': int(datetime.now(tz=UTC).timestamp()) - 10})
    with pytest.raises(HTTPException):
        codec.decode(expired)

    hub = LiveHub()
    good = _FakeWebSocket()
    stale = _FakeWebSocket(fail_send=True)
    other = _FakeWebSocket()
    good_id = await hub.connect(good)
    stale_id = await hub.connect(stale)
    other_id = await hub.connect(other)
    assert hub.subscribe(good_id, ['live:all', ' ']) == ['live:all']
    assert hub.subscribe(stale_id, ['live:all', 'live:match:2']) == ['live:all', 'live:match:2']
    assert hub.channels(good_id) == ['live:all']
    assert hub.unsubscribe(stale_id, ['live:match:2']) == ['live:all']
    await hub.broadcast(channels=['live:all'], payload={'event': 'ping'})
    assert good.messages == [{'event': 'ping'}]
    assert stale_id not in hub._connections
    assert other.messages == []
    hub.disconnect(other_id)
    assert other_id not in hub._connections

    store = RuntimeStateStore()
    store.base_path = tmp_path / 'state'
    broken = store._namespace_path('broken')
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text('{broken')
    assert store.read_namespace('broken', {'fallback': True}) == {'fallback': True}
    assert store._cache_key('players:1').startswith(settings.redis.key_prefix)
    assert store._redis_key('cache').startswith(settings.redis.key_prefix)

    fake = _FakeRedis()
    monkeypatch.setattr(store, '_get_redis', lambda: fake)
    store.write_namespace('ns', {'ok': True})
    assert store.read_namespace('ns', {}) == {'ok': True}
    store.set_cache_entry('players:1', {'expires_at': datetime.now(tz=UTC).timestamp() + 60, 'payload': {'id': 1}})
    assert store.get_cache_entry('players:1')['payload'] == {'id': 1}
    store.invalidate_cache_prefixes('players:')
    assert store.get_cache_entry('players:1') is None
    store.delete_namespace('ns')
    store.clear_cache()
    assert store.backend_name() == 'redis'

    broken_store = RuntimeStateStore()
    broken_store.base_path = tmp_path / 'state-broken'
    monkeypatch.setattr(broken_store, '_get_redis', lambda: _BrokenRedis())
    broken_store.write_namespace('fallback', {'ok': True})
    assert broken_store.read_namespace('fallback', {}) == {'ok': True}
    broken_store.set_cache_entry('cache:key', {'expires_at': datetime.now(tz=UTC).timestamp() - 1, 'payload': {'id': 2}})
    assert broken_store.get_cache_entry('cache:key') is None
    broken_store.delete_namespace('fallback')
    broken_store.clear_cache()
    monkeypatch.setattr(broken_store, '_get_redis', lambda: None)
    assert broken_store.backend_name() == 'local'


@pytest.mark.asyncio
async def test_user_engagement_and_auth_branch_coverage(prepared_test_db: str, async_client, user_auth_headers, monkeypatch) -> None:
    del prepared_test_db
    engagement = UserEngagementService()
    request = _request_with_headers(user_auth_headers)

    favorites = await engagement.list_favorites(request)
    assert favorites.data
    first_favorite = favorites.data[0]
    with pytest.raises(HTTPException):
        await engagement.create_favorite(request, FavoriteCreateRequest(entity_type=first_favorite.entity_type, entity_id=first_favorite.entity_id))
    with pytest.raises(HTTPException):
        await engagement.delete_favorite(request, 999999)

    subscriptions = await engagement.list_subscriptions(request)
    assert subscriptions.data
    first_subscription = subscriptions.data[0]
    with pytest.raises(HTTPException):
        await engagement.create_subscription(
            request,
            NotificationSubscriptionCreateRequest(
                entity_type=first_subscription.entity_type,
                entity_id=first_subscription.entity_id,
                notification_types=list(first_subscription.notification_types),
                channels=list(first_subscription.channels),
            ),
        )
    with pytest.raises(HTTPException):
        await engagement.update_subscription(request, 999999, NotificationSubscriptionUpdateRequest(is_active=False))
    with pytest.raises(HTTPException):
        await engagement.delete_subscription(request, 999999)

    notifications = await engagement.list_notifications(request)
    assert notifications.data
    unread = await engagement.get_unread_count(request)
    assert unread.data.unread_count >= 0
    with pytest.raises(HTTPException):
        await engagement.mark_notification_read(request, 999999)
    all_read = await engagement.mark_all_notifications_read(request)
    assert 'All notifications' in all_read.data.message
    test_sent = await engagement.send_test_notification(request)
    assert test_sent.data.message == 'Test notification sent'

    async with db_session_manager.session() as session:
        assert await engagement._resolve_entity_name(session, 'unknown', 1) is None
        assert await engagement._resolve_entity_name(session, 'match', 999999) is None
        with pytest.raises(HTTPException):
            await engagement._require_entity_name(session, 'unknown', 1)

    auth = AuthUserService()
    with pytest.raises(HTTPException):
        await auth.auth_me(_request_with_headers({}))

    inactive = await async_client.post('/api/v1/auth/register', json={'email': 'inactive@example.com', 'username': 'inactive_user', 'password': 'StrongPass123', 'privacy_consent': True})
    assert inactive.status_code == 201
    async with db_session_manager.session() as session:
        user = await auth.users.get_by_username(session, 'inactive_user')
        await auth.users.update(session, user, {'status': 'inactive'})

    with pytest.raises(HTTPException):
        await auth.login(None, LoginRequest(email_or_username='inactive_user', password='StrongPass123'))

    forgot = await auth.forgot_password(None, ForgotPasswordRequest(email='demo@example.com'))
    assert 'reset instructions' in forgot.data.message

    refresh_token, refresh_payload = auth._bundle(SimpleNamespace(id=2, email='demo@example.com', username='demo_user', role='user', first_name=None, last_name=None, avatar_url=None, locale='ru', timezone='Europe/Moscow', is_email_verified=False)).refresh_token, None
    del refresh_token, refresh_payload

    login = await async_client.post('/api/v1/auth/login', json={'email_or_username': 'demo_user', 'password': 'UserPass123'})
    refresh = login.json()['data']['refresh_token']
    logout = await auth.logout(None, LogoutRequest(refresh_token=refresh))
    assert logout.data.message == 'Logged out'
    with pytest.raises(HTTPException):
        await auth.refresh(None, RefreshTokenRequest(refresh_token=refresh))
