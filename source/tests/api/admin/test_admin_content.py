from fastapi import status

from source.config.settings import settings


async def test_admin_players_crud_flow(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players",
        json={"first_name": "Carlos", "last_name": "Alcaraz", "full_name": "Carlos Alcaraz", "slug": "carlos-alcaraz", "country_code": "ESP", "current_rank": 3},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    player_id = create_response.json()["data"]["id"]

    patch_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players/{player_id}",
        json={"current_points": 7800, "status": "active"},
        headers=admin_auth_headers,
    )
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.json()["data"]["current_points"] == 7800

    delete_response = await async_client.delete(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players/{player_id}", headers=admin_auth_headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert delete_response.json()["data"]["message"] == "Player deleted"


async def test_admin_tournaments_crud_flow(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tournaments",
        json={"name": "Monte Carlo 2026", "slug": "monte-carlo-2026", "category": "masters_1000", "surface": "clay", "season_year": 2026, "country_code": "MCO"},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    tournament_id = create_response.json()["data"]["id"]

    patch_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tournaments/{tournament_id}",
        json={"status": "published", "city": "Monte Carlo"},
        headers=admin_auth_headers,
    )
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.json()["data"]["status"] == "published"

    delete_response = await async_client.delete(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tournaments/{tournament_id}", headers=admin_auth_headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert delete_response.json()["data"]["message"] == "Tournament deleted"


async def test_admin_matches_crud_and_actions_flow(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches",
        json={"slug": "test-match", "tournament_id": 1, "player1_id": 1, "player2_id": 2, "status": "scheduled", "scheduled_at": "2026-03-10T12:00:00+00:00"},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    match_id = create_response.json()["data"]["id"]

    status_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/{match_id}/status",
        json={"status": "live"},
        headers=admin_auth_headers,
    )
    assert status_response.status_code == status.HTTP_200_OK
    assert status_response.json()["data"]["status"] == "live"

    score_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/{match_id}/score",
        json={"score_summary": "6-4 2-1", "sets": []},
        headers=admin_auth_headers,
    )
    assert score_response.status_code == status.HTTP_200_OK
    assert score_response.json()["data"]["score_summary"] == "6-4 2-1"

    finalize_response = await async_client.post(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/{match_id}/finalize", headers=admin_auth_headers)
    assert finalize_response.status_code == status.HTTP_200_OK
    assert finalize_response.json()["data"]["message"] == "Match finalized and post-processing queued"

    delete_response = await async_client.delete(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches/{match_id}", headers=admin_auth_headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert delete_response.json()["data"]["message"] == "Match deleted"


async def test_admin_news_crud_and_publish_flow(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news",
        json={"slug": "new-admin-article", "title": "Admin article", "content_html": "<p>Body</p>", "status": "draft"},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    news_id = create_response.json()["data"]["id"]

    patch_response = await async_client.patch(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news/{news_id}",
        json={"slug": "new-admin-article", "title": "Updated admin article", "content_html": "<p>Updated</p>", "status": "review"},
        headers=admin_auth_headers,
    )
    assert patch_response.status_code == status.HTTP_200_OK
    assert patch_response.json()["data"]["title"] == "Updated admin article"

    publish_response = await async_client.post(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news/{news_id}/publish", headers=admin_auth_headers)
    assert publish_response.status_code == status.HTTP_200_OK
    assert publish_response.json()["data"]["message"] == "News published"

    delete_response = await async_client.delete(f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news/{news_id}", headers=admin_auth_headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert delete_response.json()["data"]["message"] == "News deleted"
