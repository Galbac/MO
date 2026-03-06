from fastapi import HTTPException

from source.integrations import ProviderPayloadMapper


def test_rankings_provider_contract_normalizes_payload() -> None:
    mapper = ProviderPayloadMapper()

    rows = mapper.parse_rankings(
        'rankings-provider',
        {
            'ranking_type': 'atp',
            'ranking_date': '2026-03-06',
            'entries': [
                {'rank': 2, 'player': 'Jannik Sinner', 'country': 'it', 'points': 8010},
                {'position': 1, 'player_name': 'Novak Djokovic', 'country_code': 'rs', 'points': 9050, 'movement': 1},
            ],
        },
    )

    assert [item.position for item in rows] == [1, 2]
    assert rows[0].country_code == 'RS'
    assert rows[1].player_name == 'Jannik Sinner'


def test_live_provider_contract_normalizes_payload() -> None:
    mapper = ProviderPayloadMapper()

    events = mapper.parse_live_events(
        'live-provider',
        {
            'events': [
                {
                    'type': 'score_updated',
                    'timestamp': '2026-03-06T10:00:00Z',
                    'match': {'slug': 'novak-djokovic-vs-jannik-sinner', 'status': 'live', 'tournament_name': 'Australian Open', 'score_summary': '6-4 4-3'},
                    'players': [{'name': 'Novak Djokovic'}, {'name': 'Jannik Sinner'}],
                }
            ]
        },
    )

    assert len(events) == 1
    assert events[0].event_type == 'score_updated'
    assert events[0].tournament_name == 'Australian Open'
    assert events[0].occurred_at.isoformat().startswith('2026-03-06T10:00:00+00:00')


def test_provider_contract_rejects_incomplete_payload() -> None:
    mapper = ProviderPayloadMapper()

    try:
        mapper.parse_live_events('live-provider', {'events': [{'type': 'score_updated'}]})
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError('Expected HTTPException for invalid provider payload')
