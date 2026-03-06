import json
from pathlib import Path

from source.config.settings import settings


def _cache_payload() -> dict:
    cache_path = Path(settings.cache.storage_path)
    if not cache_path.exists():
        return {}
    return json.loads(cache_path.read_text())


async def test_public_read_side_populates_cache(async_client) -> None:
    players_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/players")
    assert players_response.status_code == 200

    player_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/players/1")
    assert player_response.status_code == 200

    rankings_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/rankings/current")
    assert rankings_response.status_code == 200

    cache_payload = _cache_payload()
    assert any(key.startswith('players:list:') for key in cache_payload)
    assert 'players:detail:1' in cache_payload
    assert any(key.startswith('rankings:current:') for key in cache_payload)


async def test_admin_mutation_invalidates_related_cache(async_client, admin_auth_headers) -> None:
    players_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/players")
    assert players_response.status_code == 200
    warm_cache = _cache_payload()
    warm_list_keys = {key for key in warm_cache if key.startswith('players:list:')}
    assert warm_list_keys

    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players",
        headers=admin_auth_headers,
        json={
            'slug': 'cache-player',
            'first_name': 'Cache',
            'last_name': 'Player',
            'full_name': 'Cache Player',
            'country_code': 'US',
            'country_name': 'United States',
            'status': 'active',
            'current_rank': 77,
            'current_points': 900,
        },
    )
    assert create_response.status_code == 200

    cache_payload = _cache_payload()
    assert not any(key in cache_payload for key in warm_list_keys)
    assert any(key.startswith('players:detail:') for key in cache_payload)


async def test_ranking_admin_operations_invalidate_rankings_cache(async_client, admin_auth_headers) -> None:
    rankings_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/rankings/current")
    assert rankings_response.status_code == 200
    assert any(key.startswith('rankings:') for key in _cache_payload())

    import_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/rankings/import",
        headers=admin_auth_headers,
        json={'ranking_type': 'atp', 'source_file': 'rankings.csv'},
    )
    assert import_response.status_code == 200

    cache_payload = _cache_payload()
    assert not any(key.startswith('rankings:') for key in cache_payload)
