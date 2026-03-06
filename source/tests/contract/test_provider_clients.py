import httpx

from source.integrations import IntegrationSyncError, LiveScoreProviderClient, RankingsProviderClient


def _transport(handler):
    return httpx.MockTransport(handler)


async def test_live_provider_client_fetches_and_normalizes() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            'events': [
                {
                    'type': 'score_updated',
                    'timestamp': '2026-03-06T10:00:00Z',
                    'match': {'slug': 'novak-djokovic-vs-jannik-sinner', 'status': 'live', 'tournament_name': 'Australian Open'},
                    'players': [{'name': 'Novak Djokovic'}, {'name': 'Jannik Sinner'}],
                }
            ]
        })

    client = LiveScoreProviderClient('live-provider', transport=_transport(handler))
    events = await client.fetch_events('https://provider.test/live')
    assert len(events) == 1
    assert events[0].event_type == 'score_updated'


async def test_rankings_provider_client_retries_and_fetches() -> None:
    attempts = {'count': 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts['count'] += 1
        if attempts['count'] == 1:
            return httpx.Response(503, json={'error': 'temporary'})
        return httpx.Response(200, json={
            'ranking_type': 'atp',
            'ranking_date': '2026-03-06',
            'entries': [{'position': 1, 'player_name': 'Novak Djokovic', 'country_code': 'RS', 'points': 9000}],
        })

    client = RankingsProviderClient('rankings-provider', transport=_transport(handler))
    rows = await client.fetch_rankings('https://provider.test/rankings')
    assert attempts['count'] == 2
    assert rows[0].player_name == 'Novak Djokovic'


async def test_provider_client_maps_failure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={'error': 'boom'})

    client = LiveScoreProviderClient('live-provider', transport=_transport(handler), max_attempts=2)
    try:
        await client.fetch_events('https://provider.test/live')
    except IntegrationSyncError as exc:
        assert 'server error 500' in str(exc)
    else:
        raise AssertionError('Expected IntegrationSyncError')
