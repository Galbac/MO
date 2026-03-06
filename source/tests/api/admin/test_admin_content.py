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

    draw_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tournaments/{tournament_id}/draw/generate",
        headers=admin_auth_headers,
    )
    assert draw_response.status_code == status.HTTP_200_OK
    assert "Draw generated" in draw_response.json()["data"]["message"]

    publish_tournament_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tournaments/{tournament_id}/publish",
        headers=admin_auth_headers,
    )
    assert publish_tournament_response.status_code == status.HTTP_200_OK
    assert publish_tournament_response.json()["data"]["message"] == "Tournament published"

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


async def test_publishing_news_creates_notifications_for_related_subscribers(async_client, admin_auth_headers) -> None:
    register_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/register",
        json={
            'email': 'news-subscriber@example.com',
            'username': 'news_subscriber',
            'password': 'NewsPass123',
            'locale': 'en',
            'timezone': 'UTC',
        },
    )
    assert register_response.status_code == status.HTTP_201_CREATED

    login_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={'email_or_username': 'news_subscriber', 'password': 'NewsPass123'},
    )
    assert login_response.status_code == status.HTTP_200_OK
    user_headers = {'Authorization': f"Bearer {login_response.json()['data']['access_token']}"}

    subscribe_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/users/me/subscriptions",
        headers=user_headers,
        json={
            'entity_type': 'player',
            'entity_id': 1,
            'notification_types': ['news'],
            'channels': ['web'],
        },
    )
    assert subscribe_response.status_code == status.HTTP_200_OK

    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news",
        json={
            'slug': 'djokovic-notification-article',
            'title': 'Novak Djokovic prepares for another title run',
            'lead': 'Detailed match analysis for Novak Djokovic.',
            'content_html': '<p>Novak Djokovic is back on court with fresh momentum.</p>',
            'status': 'draft',
        },
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    news_id = create_response.json()['data']['id']

    publish_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news/{news_id}/publish",
        headers=admin_auth_headers,
    )
    assert publish_response.status_code == status.HTTP_200_OK

    notifications_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/notifications",
        headers=user_headers,
    )
    assert notifications_response.status_code == status.HTTP_200_OK
    assert any(
        item['type'] == 'news'
        and item['title'] == 'Novak Djokovic prepares for another title run'
        and item['payload_json']['slug'] == 'djokovic-notification-article'
        for item in notifications_response.json()['data']
    )



async def test_admin_players_import_photo_and_recalculate_flow(async_client, admin_auth_headers) -> None:
    import_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players/import",
        json={
            "players": [
                {
                    "first_name": "Casper",
                    "last_name": "Ruud",
                    "full_name": "Casper Ruud",
                    "slug": "casper-ruud",
                    "country_code": "NOR",
                    "current_rank": 8,
                }
            ]
        },
        headers=admin_auth_headers,
    )
    assert import_response.status_code == status.HTTP_200_OK
    assert import_response.json()["data"]["message"] == "Imported 1 players"

    players_response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players",
        headers=admin_auth_headers,
    )
    imported = next(item for item in players_response.json()["data"] if item["slug"] == "casper-ruud")

    photo_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players/{imported['id']}/photo",
        json={"photo_url": "https://example.com/ruud.jpg"},
        headers=admin_auth_headers,
    )
    assert photo_response.status_code == status.HTTP_200_OK
    assert photo_response.json()["data"]["message"] == "Player photo updated"

    recalc_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players/{imported['id']}/recalculate-stats",
        headers=admin_auth_headers,
    )
    assert recalc_response.status_code == status.HTTP_200_OK
    assert "Player stats recalculated via job" in recalc_response.json()["data"]["message"]



async def test_admin_news_cover_and_tags_flow(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news",
        json={"slug": "tagged-admin-article", "title": "Tagged article", "content_html": "<p>Body</p>", "status": "draft"},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK
    news_id = create_response.json()["data"]["id"]

    cover_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news/{news_id}/cover",
        json={"cover_image_url": "https://example.com/cover.jpg"},
        headers=admin_auth_headers,
    )
    assert cover_response.status_code == status.HTTP_200_OK
    assert cover_response.json()["data"]["message"] == "News cover updated"

    tags_list = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news/tags/list",
        headers=admin_auth_headers,
    )
    assert tags_list.status_code == status.HTTP_200_OK
    tag_ids = [item["id"] for item in tags_list.json()["data"][:2]]

    tags_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news/{news_id}/tags",
        json={"tag_ids": tag_ids},
        headers=admin_auth_headers,
    )
    assert tags_response.status_code == status.HTTP_200_OK
    assert len(tags_response.json()["data"]) == len(tag_ids)

    article_response = await async_client.get(f"{settings.api.prefix}{settings.api.v1.prefix}/news/tagged-admin-article")
    assert article_response.status_code == status.HTTP_200_OK
    assert len(article_response.json()["data"]["tags"]) == len(tag_ids)
    assert article_response.json()["data"]["cover_image_url"] == "https://example.com/cover.jpg"



async def test_admin_players_support_filters(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players",
        json={"first_name": "Filter", "last_name": "Player", "full_name": "Filter Player", "slug": "filter-player", "country_code": "FRA", "hand": "left", "status": "active"},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK

    response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/players",
        params={"search": "Filter", "country_code": "FRA", "hand": "left", "status": "active"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload
    assert any(item["slug"] == "filter-player" for item in payload)



async def test_admin_tournaments_support_filters(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tournaments",
        json={"name": "Rome Masters 2026", "slug": "rome-masters-2026", "category": "masters_1000", "surface": "clay", "season_year": 2026, "status": "scheduled", "city": "Rome", "country_code": "ITA"},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK

    response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/tournaments",
        params={"search": "Rome", "category": "masters_1000", "surface": "clay", "status": "scheduled", "season_year": 2026},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload
    assert any(item["slug"] == "rome-masters-2026" for item in payload)


async def test_admin_matches_support_filters(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches",
        json={
            "slug": "filter-match-finals",
            "tournament_id": 1,
            "player1_id": 1,
            "player2_id": 2,
            "status": "scheduled",
            "round_code": "F",
            "scheduled_at": "2026-03-15T12:00:00+00:00",
        },
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK

    response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/matches",
        params={
            "search": "filter-match",
            "status": "scheduled",
            "tournament_id": 1,
            "player_id": 1,
            "round_code": "F",
            "date_from": "2026-03-15",
            "date_to": "2026-03-15",
        },
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload
    assert any(item["slug"] == "filter-match-finals" for item in payload)


async def test_admin_news_support_filters(async_client, admin_auth_headers) -> None:
    create_response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news",
        json={"slug": "filtered-admin-news", "title": "Filtered Admin Story", "content_html": "<p>Body</p>", "status": "draft"},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == status.HTTP_200_OK

    response = await async_client.get(
        f"{settings.api.prefix}{settings.api.v1.prefix}/admin/news",
        params={"search": "Filtered", "status": "draft"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert any(item["slug"] == "filtered-admin-news" for item in payload)
