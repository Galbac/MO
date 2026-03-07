from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient

from source.config.settings import settings
from source.main import create_app
from source.services.auth_user_service import AuthUserService
from source.services.job_service import JobService


API_PREFIX = f"{settings.api.prefix}{settings.api.v1.prefix}"


def _http_route_set() -> set[tuple[str, str]]:
    app = create_app()
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(API_PREFIX):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            routes.add((method, route.path))
    return routes


def _ws_route_set() -> set[str]:
    app = create_app()
    return {
        route.path
        for route in app.routes
        if isinstance(route, APIWebSocketRoute) and route.path.startswith(API_PREFIX)
    }


async def test_api_http_route_smoke_matrix(async_client, admin_auth_headers) -> None:
    visited: set[tuple[str, str]] = set()

    async def hit(
        method: str,
        template: str,
        *,
        url: str | None = None,
        headers: dict[str, str] | None = None,
        json: dict | list | None = None,
        params: dict | None = None,
        files: dict | None = None,
        expected_status: int = 200,
    ):
        response = await async_client.request(method, url or template, headers=headers, json=json, params=params, files=files)
        assert response.status_code == expected_status, response.text
        visited.add((method.upper(), template))
        return response

    unique = uuid4().hex[:8]
    auth_username = f"route_user_{unique}"
    auth_email = f"{auth_username}@example.com"
    auth_password = "StrongPass123"

    await hit("GET", f"{API_PREFIX}/health")
    await hit("GET", f"{API_PREFIX}/health/ready")

    register_response = await hit(
        "POST",
        f"{API_PREFIX}/auth/register",
        json={
            "email": auth_email,
            "username": auth_username,
            "password": auth_password,
            "locale": "ru",
            "timezone": "Europe/Moscow",
            "privacy_consent": True,
        },
        expected_status=201,
    )
    auth_user_id = register_response.json()["data"]["user"]["id"]

    login_response = await hit(
        "POST",
        f"{API_PREFIX}/auth/login",
        json={"email_or_username": auth_username, "password": auth_password},
    )
    access_token = login_response.json()["data"]["access_token"]
    refresh_token = login_response.json()["data"]["refresh_token"]
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    await hit("GET", f"{API_PREFIX}/auth/me", headers=auth_headers)
    refresh_response = await hit(
        "POST",
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    refreshed_token = refresh_response.json()["data"]["refresh_token"]
    await hit("POST", f"{API_PREFIX}/auth/logout", json={"refresh_token": refreshed_token})

    forgot_response = await hit(
        "POST",
        f"{API_PREFIX}/auth/forgot-password",
        json={"email": auth_email},
    )
    assert forgot_response.json()["success"] is True

    auth_service = AuthUserService()
    reset_token = auth_service._issue_action_token(
        user_id=auth_user_id,
        purpose="password_reset",
        ttl_minutes=settings.auth.password_reset_token_ttl_minutes,
    )
    new_password = "NewStrongPass456"
    await hit(
        "POST",
        f"{API_PREFIX}/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )

    verify_token = auth_service._issue_action_token(
        user_id=auth_user_id,
        purpose="verify_email",
        ttl_minutes=settings.auth.email_verification_token_ttl_minutes,
    )
    await hit(
        "POST",
        f"{API_PREFIX}/auth/verify-email",
        json={"token": verify_token},
    )

    relogin_response = await async_client.post(
        f"{API_PREFIX}/auth/login",
        json={"email_or_username": auth_username, "password": new_password},
    )
    assert relogin_response.status_code == 200, relogin_response.text
    user_headers = {"Authorization": f"Bearer {relogin_response.json()['data']['access_token']}"}

    await hit("GET", f"{API_PREFIX}/users/me", headers=user_headers)
    await hit(
        "PATCH",
        f"{API_PREFIX}/users/me",
        headers=user_headers,
        json={"first_name": "Маршрут", "timezone": "UTC", "quiet_hours_start": "23:00", "quiet_hours_end": "07:00"},
    )
    await hit(
        "PATCH",
        f"{API_PREFIX}/users/me/password",
        headers=user_headers,
        json={"current_password": new_password, "new_password": auth_password},
    )

    password_login = await async_client.post(
        f"{API_PREFIX}/auth/login",
        json={"email_or_username": auth_username, "password": auth_password},
    )
    assert password_login.status_code == 200, password_login.text
    user_headers = {"Authorization": f"Bearer {password_login.json()['data']['access_token']}"}

    await hit("GET", f"{API_PREFIX}/users/me/favorites", headers=user_headers)
    await hit("GET", f"{API_PREFIX}/users/me/smart-feed", headers=user_headers)
    await hit("GET", f"{API_PREFIX}/users/me/calendar", headers=user_headers)
    favorite_response = await hit(
        "POST",
        f"{API_PREFIX}/users/me/favorites",
        headers=user_headers,
        json={"entity_type": "news", "entity_id": 1},
    )
    favorite_id = favorite_response.json()["data"]["id"]
    await hit(
        "DELETE",
        f"{API_PREFIX}/users/me/favorites/{{favorite_id}}",
        url=f"{API_PREFIX}/users/me/favorites/{favorite_id}",
        headers=user_headers,
    )
    reminder_response = await hit(
        "POST",
        f"{API_PREFIX}/users/me/calendar/reminders",
        headers=user_headers,
        json={"match_id": 2, "remind_before_minutes": 45, "channel": "web"},
    )
    reminder_id = reminder_response.json()["data"]["id"]
    await hit(
        "PATCH",
        f"{API_PREFIX}/users/me/calendar/reminders/{{reminder_id}}",
        url=f"{API_PREFIX}/users/me/calendar/reminders/{reminder_id}",
        headers=user_headers,
        json={"remind_before_minutes": 60, "is_active": False},
    )
    await hit(
        "DELETE",
        f"{API_PREFIX}/users/me/calendar/reminders/{{reminder_id}}",
        url=f"{API_PREFIX}/users/me/calendar/reminders/{reminder_id}",
        headers=user_headers,
    )

    await hit("GET", f"{API_PREFIX}/users/me/subscriptions", headers=user_headers)
    subscription_response = await hit(
        "POST",
        f"{API_PREFIX}/users/me/subscriptions",
        headers=user_headers,
        json={
            "entity_type": "match",
            "entity_id": 2,
            "notification_types": ["match_start"],
            "channels": ["web"],
        },
    )
    subscription_id = subscription_response.json()["data"]["id"]
    await hit(
        "PATCH",
        f"{API_PREFIX}/users/me/subscriptions/{{subscription_id}}",
        url=f"{API_PREFIX}/users/me/subscriptions/{subscription_id}",
        headers=user_headers,
        json={"is_active": False},
    )
    await hit(
        "DELETE",
        f"{API_PREFIX}/users/me/subscriptions/{{subscription_id}}",
        url=f"{API_PREFIX}/users/me/subscriptions/{subscription_id}",
        headers=user_headers,
    )

    await hit("GET", f"{API_PREFIX}/users/me/notifications", headers=user_headers)
    await hit("GET", f"{API_PREFIX}/users/me/push-subscriptions", headers=user_headers)
    push_response = await hit(
        "POST",
        f"{API_PREFIX}/users/me/push-subscriptions",
        headers=user_headers,
        json={"endpoint": f"browser://matrix/{unique}", "device_label": "route-matrix", "keys_json": {"auth": "token"}, "permission": "granted"},
    )
    push_id = push_response.json()["data"]["id"]
    await hit("POST", f"{API_PREFIX}/users/me/push-subscriptions/test", headers=user_headers, json={"title": "Проверка", "body": "Push канал активен"})
    await hit("POST", f"{API_PREFIX}/notifications/test", headers=user_headers)
    notifications_response = await hit("GET", f"{API_PREFIX}/notifications", headers=user_headers)
    notification_id = notifications_response.json()["data"][0]["id"]
    await hit("GET", f"{API_PREFIX}/notifications/unread-count", headers=user_headers)
    await hit(
        "PATCH",
        f"{API_PREFIX}/notifications/{{notification_id}}/read",
        url=f"{API_PREFIX}/notifications/{notification_id}/read",
        headers=user_headers,
    )
    await hit("PATCH", f"{API_PREFIX}/notifications/read-all", headers=user_headers)

    user_notifications = await hit("GET", f"{API_PREFIX}/users/me/notifications", headers=user_headers)
    user_notification_id = user_notifications.json()["data"][0]["id"]
    await hit(
        "PATCH",
        f"{API_PREFIX}/users/me/notifications/{{notification_id}}/read",
        url=f"{API_PREFIX}/users/me/notifications/{user_notification_id}/read",
        headers=user_headers,
    )
    await hit("PATCH", f"{API_PREFIX}/users/me/notifications/read-all", headers=user_headers)
    await hit(
        "DELETE",
        f"{API_PREFIX}/users/me/push-subscriptions/{{subscription_id}}",
        url=f"{API_PREFIX}/users/me/push-subscriptions/{push_id}",
        headers=user_headers,
    )

    await hit("GET", f"{API_PREFIX}/players")
    await hit("GET", f"{API_PREFIX}/players/compare", params={"player1_id": 1, "player2_id": 2})
    await hit("GET", f"{API_PREFIX}/players/h2h", params={"player1_id": 1, "player2_id": 2})
    await hit("GET", f"{API_PREFIX}/players/{{player_id}}", url=f"{API_PREFIX}/players/1")
    await hit("GET", f"{API_PREFIX}/players/{{player_id}}/stats", url=f"{API_PREFIX}/players/1/stats")
    await hit("GET", f"{API_PREFIX}/players/{{player_id}}/matches", url=f"{API_PREFIX}/players/1/matches")
    await hit("GET", f"{API_PREFIX}/players/{{player_id}}/ranking-history", url=f"{API_PREFIX}/players/1/ranking-history")
    await hit("GET", f"{API_PREFIX}/players/{{player_id}}/titles", url=f"{API_PREFIX}/players/1/titles")
    await hit("GET", f"{API_PREFIX}/players/{{player_id}}/news", url=f"{API_PREFIX}/players/1/news")
    await hit("GET", f"{API_PREFIX}/players/{{player_id}}/upcoming-matches", url=f"{API_PREFIX}/players/1/upcoming-matches")

    await hit("GET", f"{API_PREFIX}/tournaments")
    await hit("GET", f"{API_PREFIX}/tournaments/{{tournament_id}}", url=f"{API_PREFIX}/tournaments/1")
    await hit("GET", f"{API_PREFIX}/tournaments/{{tournament_id}}/matches", url=f"{API_PREFIX}/tournaments/1/matches")
    await hit("GET", f"{API_PREFIX}/tournaments/{{tournament_id}}/draw", url=f"{API_PREFIX}/tournaments/1/draw")
    await hit("GET", f"{API_PREFIX}/tournaments/{{tournament_id}}/players", url=f"{API_PREFIX}/tournaments/1/players")
    await hit("GET", f"{API_PREFIX}/tournaments/{{tournament_id}}/champions", url=f"{API_PREFIX}/tournaments/1/champions")
    await hit("GET", f"{API_PREFIX}/tournaments/{{tournament_id}}/news", url=f"{API_PREFIX}/tournaments/1/news")
    await hit("GET", f"{API_PREFIX}/tournaments/calendar")

    await hit("GET", f"{API_PREFIX}/matches")
    await hit("GET", f"{API_PREFIX}/matches/{{match_id}}", url=f"{API_PREFIX}/matches/1")
    await hit("GET", f"{API_PREFIX}/matches/{{match_id}}/score", url=f"{API_PREFIX}/matches/1/score")
    await hit("GET", f"{API_PREFIX}/matches/{{match_id}}/stats", url=f"{API_PREFIX}/matches/1/stats")
    await hit("GET", f"{API_PREFIX}/matches/{{match_id}}/timeline", url=f"{API_PREFIX}/matches/1/timeline")
    await hit("GET", f"{API_PREFIX}/matches/{{match_id}}/h2h", url=f"{API_PREFIX}/matches/1/h2h")
    await hit("GET", f"{API_PREFIX}/matches/{{match_id}}/preview", url=f"{API_PREFIX}/matches/1/preview")
    await hit("GET", f"{API_PREFIX}/matches/{{match_id}}/prediction", url=f"{API_PREFIX}/matches/1/prediction")
    await hit("GET", f"{API_PREFIX}/matches/{{match_id}}/momentum", url=f"{API_PREFIX}/matches/2/momentum")
    await hit("GET", f"{API_PREFIX}/matches/{{match_id}}/point-by-point", url=f"{API_PREFIX}/matches/1/point-by-point")
    await hit("GET", f"{API_PREFIX}/matches/upcoming")
    await hit("GET", f"{API_PREFIX}/matches/results")

    await hit("GET", f"{API_PREFIX}/live")
    await hit("GET", f"{API_PREFIX}/live/feed")
    await hit("GET", f"{API_PREFIX}/live/{{match_id}}", url=f"{API_PREFIX}/live/2")

    await hit("GET", f"{API_PREFIX}/rankings")
    await hit("GET", f"{API_PREFIX}/rankings/current", params={"ranking_type": "atp"})
    await hit("GET", f"{API_PREFIX}/rankings/{{ranking_type}}/history", url=f"{API_PREFIX}/rankings/atp/history")
    await hit("GET", f"{API_PREFIX}/rankings/player/{{player_id}}", url=f"{API_PREFIX}/rankings/player/1")
    await hit("GET", f"{API_PREFIX}/rankings/race")

    await hit("GET", f"{API_PREFIX}/news")
    await hit("GET", f"{API_PREFIX}/news/categories")
    await hit("GET", f"{API_PREFIX}/news/tags")
    await hit("GET", f"{API_PREFIX}/news/featured")
    await hit("GET", f"{API_PREFIX}/news/related", params={"slug": "djokovic-wins-ao-2026"})
    await hit("GET", f"{API_PREFIX}/news/{{slug}}", url=f"{API_PREFIX}/news/djokovic-wins-ao-2026")

    await hit("GET", f"{API_PREFIX}/search", params={"q": "Djokovic"})
    await hit("GET", f"{API_PREFIX}/search/suggestions", params={"q": "Djoko"})

    media_upload_response = await hit(
        "POST",
        f"{API_PREFIX}/media/upload",
        headers=admin_auth_headers,
        files={"file": ("cover.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9", "image/jpeg")},
        expected_status=201,
    )
    media_id = media_upload_response.json()["data"]["id"]
    await hit("GET", f"{API_PREFIX}/media/{{media_id}}", url=f"{API_PREFIX}/media/{media_id}")
    await hit("DELETE", f"{API_PREFIX}/media/{{media_id}}", url=f"{API_PREFIX}/media/{media_id}", headers=admin_auth_headers)

    temp_user_response = await async_client.post(
        f"{API_PREFIX}/auth/register",
        json={
            "email": f"admin-managed-{unique}@example.com",
            "username": f"admin_managed_{unique}",
            "password": "AdminManaged123",
            "locale": "ru",
            "timezone": "Europe/Moscow",
            "privacy_consent": True,
        },
    )
    assert temp_user_response.status_code == 201, temp_user_response.text
    temp_user_id = temp_user_response.json()["data"]["user"]["id"]

    await hit("GET", f"{API_PREFIX}/admin/users", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/users/{{user_id}}", url=f"{API_PREFIX}/admin/users/{temp_user_id}", headers=admin_auth_headers)
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/users/{{user_id}}",
        url=f"{API_PREFIX}/admin/users/{temp_user_id}",
        headers=admin_auth_headers,
        json={"first_name": "Админ", "last_name": "Проверка"},
    )
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/users/{{user_id}}/status",
        url=f"{API_PREFIX}/admin/users/{temp_user_id}/status",
        headers=admin_auth_headers,
        json={"status": "active"},
    )
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/users/{{user_id}}/role",
        url=f"{API_PREFIX}/admin/users/{temp_user_id}/role",
        headers=admin_auth_headers,
        json={"role": "editor"},
    )

    await hit("GET", f"{API_PREFIX}/admin/players", headers=admin_auth_headers)
    player_response = await hit(
        "POST",
        f"{API_PREFIX}/admin/players",
        headers=admin_auth_headers,
        json={
            "first_name": "Route",
            "last_name": "Player",
            "full_name": "Route Player",
            "slug": f"route-player-{unique}",
            "country_code": "RUS",
            "current_rank": 55,
        },
    )
    player_id = player_response.json()["data"]["id"]
    await hit("GET", f"{API_PREFIX}/admin/players/{{player_id}}", url=f"{API_PREFIX}/admin/players/{player_id}", headers=admin_auth_headers)
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/players/{{player_id}}",
        url=f"{API_PREFIX}/admin/players/{player_id}",
        headers=admin_auth_headers,
        json={"current_points": 1234, "status": "active"},
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/players/import",
        headers=admin_auth_headers,
        json={
            "players": [
                {
                    "first_name": "Import",
                    "last_name": "Player",
                    "full_name": f"Import Player {unique}",
                    "slug": f"import-player-{unique}",
                    "country_code": "ESP",
                    "current_rank": 88,
                }
            ]
        },
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/players/{{player_id}}/photo",
        url=f"{API_PREFIX}/admin/players/{player_id}/photo",
        headers=admin_auth_headers,
        json={"photo_url": "https://example.com/player.jpg"},
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/players/{{player_id}}/recalculate-stats",
        url=f"{API_PREFIX}/admin/players/{player_id}/recalculate-stats",
        headers=admin_auth_headers,
    )

    await hit("GET", f"{API_PREFIX}/admin/tournaments", headers=admin_auth_headers)
    tournament_response = await hit(
        "POST",
        f"{API_PREFIX}/admin/tournaments",
        headers=admin_auth_headers,
        json={
            "name": f"Route Tournament {unique}",
            "slug": f"route-tournament-{unique}",
            "category": "atp_250",
            "surface": "hard",
            "season_year": 2026,
            "country_code": "RUS",
        },
    )
    tournament_id = tournament_response.json()["data"]["id"]
    await hit("GET", f"{API_PREFIX}/admin/tournaments/{{tournament_id}}", url=f"{API_PREFIX}/admin/tournaments/{tournament_id}", headers=admin_auth_headers)
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/tournaments/{{tournament_id}}",
        url=f"{API_PREFIX}/admin/tournaments/{tournament_id}",
        headers=admin_auth_headers,
        json={"city": "Махачкала", "status": "published"},
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/tournaments/{{tournament_id}}/draw/generate",
        url=f"{API_PREFIX}/admin/tournaments/{tournament_id}/draw/generate",
        headers=admin_auth_headers,
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/tournaments/{{tournament_id}}/publish",
        url=f"{API_PREFIX}/admin/tournaments/{tournament_id}/publish",
        headers=admin_auth_headers,
    )

    await hit("GET", f"{API_PREFIX}/admin/matches", headers=admin_auth_headers)
    match_response = await hit(
        "POST",
        f"{API_PREFIX}/admin/matches",
        headers=admin_auth_headers,
        json={
            "slug": f"route-match-{unique}",
            "tournament_id": tournament_id,
            "player1_id": 1,
            "player2_id": 2,
            "status": "scheduled",
            "scheduled_at": "2026-03-10T12:00:00+00:00",
        },
    )
    match_id = match_response.json()["data"]["id"]
    await hit("GET", f"{API_PREFIX}/admin/matches/{{match_id}}", url=f"{API_PREFIX}/admin/matches/{match_id}", headers=admin_auth_headers)
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/matches/{{match_id}}",
        url=f"{API_PREFIX}/admin/matches/{match_id}",
        headers=admin_auth_headers,
        json={"court_name": "Center Court", "best_of_sets": 3},
    )
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/matches/{{match_id}}/status",
        url=f"{API_PREFIX}/admin/matches/{match_id}/status",
        headers=admin_auth_headers,
        json={"status": "live"},
    )
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/matches/{{match_id}}/score",
        url=f"{API_PREFIX}/admin/matches/{match_id}/score",
        headers=admin_auth_headers,
        json={
            "score_summary": "6-4 6-3",
            "sets": [
                {"set_number": 1, "player1_games": 6, "player2_games": 4, "is_finished": True},
                {"set_number": 2, "player1_games": 6, "player2_games": 3, "is_finished": True},
            ],
        },
    )
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/matches/{{match_id}}/stats",
        url=f"{API_PREFIX}/admin/matches/{match_id}/stats",
        headers=admin_auth_headers,
        json={
            "stats": {
                "player1_aces": 4,
                "player2_aces": 3,
                "player1_double_faults": 1,
                "player2_double_faults": 2,
                "player1_first_serve_pct": 68,
                "player2_first_serve_pct": 64,
                "player1_break_points_saved": 3,
                "player2_break_points_saved": 2,
                "duration_minutes": 74,
                "player1_break_points_faced": 4,
                "player2_break_points_faced": 5,
            }
        },
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/matches/{{match_id}}/events",
        url=f"{API_PREFIX}/admin/matches/{match_id}/events",
        headers=admin_auth_headers,
        json={"event_type": "break", "set_number": 1, "game_number": 3, "player_id": 1, "payload_json": {"score": "30-40"}},
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/matches/{{match_id}}/finalize",
        url=f"{API_PREFIX}/admin/matches/{match_id}/finalize",
        headers=admin_auth_headers,
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/matches/{{match_id}}/reopen",
        url=f"{API_PREFIX}/admin/matches/{match_id}/reopen",
        headers=admin_auth_headers,
    )

    await hit("GET", f"{API_PREFIX}/admin/maintenance", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/maintenance/backups", headers=admin_auth_headers)
    maintenance_run = await hit(
        "POST",
        f"{API_PREFIX}/admin/maintenance/run",
        headers=admin_auth_headers,
        json={"job_type": "clear_cache", "prefixes": ["news:"]},
    )
    maintenance_job_id = maintenance_run.json()["data"]["job_id"]

    await hit("GET", f"{API_PREFIX}/admin/media", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/media/summary", headers=admin_auth_headers)
    admin_media_payload = base64.b64encode(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9").decode()
    admin_media_upload = await hit(
        "POST",
        f"{API_PREFIX}/admin/media/upload",
        headers=admin_auth_headers,
        json={
            "filename": f"admin-{unique}.jpg",
            "content_type": "image/jpeg",
            "content_base64": admin_media_payload,
            "size": 20,
        },
        expected_status=201,
    )
    admin_media_id = admin_media_upload.json()["data"]["id"]
    await hit("GET", f"{API_PREFIX}/admin/media/{{media_id}}", url=f"{API_PREFIX}/admin/media/{admin_media_id}", headers=admin_auth_headers)

    await hit("GET", f"{API_PREFIX}/admin/notifications/templates", headers=admin_auth_headers)
    await hit("POST", f"{API_PREFIX}/admin/notifications/test", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/notifications", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/notifications/summary", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/notifications/delivery-log", headers=admin_auth_headers)

    await hit("GET", f"{API_PREFIX}/admin/news", headers=admin_auth_headers)
    news_response = await hit(
        "POST",
        f"{API_PREFIX}/admin/news",
        headers=admin_auth_headers,
        json={"slug": f"route-news-{unique}", "title": "Route News", "content_html": "<p>Route body</p>", "status": "draft"},
    )
    news_id = news_response.json()["data"]["id"]
    await hit("GET", f"{API_PREFIX}/admin/news/{{news_id}}", url=f"{API_PREFIX}/admin/news/{news_id}", headers=admin_auth_headers)
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/news/{{news_id}}",
        url=f"{API_PREFIX}/admin/news/{news_id}",
        headers=admin_auth_headers,
        json={"slug": f"route-news-{unique}", "title": "Route News Updated", "content_html": "<p>Updated body</p>", "status": "review"},
    )
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/news/{{news_id}}/status",
        url=f"{API_PREFIX}/admin/news/{news_id}/status",
        headers=admin_auth_headers,
        json={"status": "review"},
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/news/{{news_id}}/schedule",
        url=f"{API_PREFIX}/admin/news/{news_id}/schedule",
        headers=admin_auth_headers,
        json={"status": "scheduled", "publish_at": "2026-03-15T10:00:00+00:00"},
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/news/{{news_id}}/cover",
        url=f"{API_PREFIX}/admin/news/{news_id}/cover",
        headers=admin_auth_headers,
        json={"cover_image_url": "https://example.com/news-cover.jpg"},
    )
    category_list = await hit("GET", f"{API_PREFIX}/admin/news/categories/list", headers=admin_auth_headers)
    assert category_list.json()["data"]
    tag_list = await hit("GET", f"{API_PREFIX}/admin/news/tags/list", headers=admin_auth_headers)
    tag_ids = [item["id"] for item in tag_list.json()["data"][:2]]
    await hit(
        "POST",
        f"{API_PREFIX}/admin/news/{{news_id}}/tags",
        url=f"{API_PREFIX}/admin/news/{news_id}/tags",
        headers=admin_auth_headers,
        json={"tag_ids": tag_ids},
    )
    await hit(
        "POST",
        f"{API_PREFIX}/admin/news/{{news_id}}/publish",
        url=f"{API_PREFIX}/admin/news/{news_id}/publish",
        headers=admin_auth_headers,
    )

    await hit("GET", f"{API_PREFIX}/admin/rankings/import-jobs", headers=admin_auth_headers)
    await hit(
        "POST",
        f"{API_PREFIX}/admin/rankings/import",
        headers=admin_auth_headers,
        json={
            "provider": "rankings-provider",
            "provider_payload": {
                "ranking_type": "atp",
                "ranking_date": "2026-03-20",
                "entries": [
                    {"position": 1, "player_name": "Jannik Sinner", "country_code": "IT", "points": 9300},
                    {"position": 2, "player_name": "Novak Djokovic", "country_code": "RS", "points": 9100},
                ],
            },
        },
    )
    await hit("POST", f"{API_PREFIX}/admin/rankings/recalculate-movements", headers=admin_auth_headers)

    await hit("GET", f"{API_PREFIX}/admin/settings", headers=admin_auth_headers)
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/settings",
        headers=admin_auth_headers,
        json={"seo_title": "Маршрут API", "support_email": "support@makhachkalaopen.ru"},
    )

    await hit("GET", f"{API_PREFIX}/admin/integrations", headers=admin_auth_headers)
    provider = "rankings-provider"
    await hit("GET", f"{API_PREFIX}/admin/integrations/summary", headers=admin_auth_headers)
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/integrations/{{provider}}",
        url=f"{API_PREFIX}/admin/integrations/{provider}",
        headers=admin_auth_headers,
        json={"endpoint": "https://example.com/feed.json", "api_key": "demo-key"},
    )
    await hit("GET", f"{API_PREFIX}/admin/integrations/{{provider}}", url=f"{API_PREFIX}/admin/integrations/{provider}", headers=admin_auth_headers)
    await hit(
        "POST",
        f"{API_PREFIX}/admin/integrations/{{provider}}/sync",
        url=f"{API_PREFIX}/admin/integrations/{provider}/sync",
        headers=admin_auth_headers,
        json={"provider_payload": {"live": []}}
        if "live" in provider
        else {
            "provider_payload": {
                "ranking_type": "atp",
                "ranking_date": "2026-03-21",
                "entries": [
                    {"position": 1, "player_name": "Jannik Sinner", "country_code": "IT", "points": 9350},
                    {"position": 2, "player_name": "Novak Djokovic", "country_code": "RS", "points": 9150},
                ],
            }
        },
    )
    await hit("GET", f"{API_PREFIX}/admin/integrations/{{provider}}/logs", url=f"{API_PREFIX}/admin/integrations/{provider}/logs", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/integrations/{{provider}}/logs/summary", url=f"{API_PREFIX}/admin/integrations/{provider}/logs/summary", headers=admin_auth_headers)

    await hit("GET", f"{API_PREFIX}/admin/jobs", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/jobs/summary", headers=admin_auth_headers)

    job_service = JobService()
    pending_job = await job_service.enqueue(
        job_type="clear_cache",
        payload={"prefixes": ["rankings:"]},
        run_at=datetime.now(tz=UTC) + timedelta(minutes=30),
    )
    pending_job_id = int(pending_job["id"])
    await hit("GET", f"{API_PREFIX}/admin/jobs/{{job_id}}", url=f"{API_PREFIX}/admin/jobs/{pending_job_id}", headers=admin_auth_headers)
    await hit("POST", f"{API_PREFIX}/admin/jobs/{{job_id}}/cancel", url=f"{API_PREFIX}/admin/jobs/{pending_job_id}/cancel", headers=admin_auth_headers)
    await hit("POST", f"{API_PREFIX}/admin/jobs/{{job_id}}/retry", url=f"{API_PREFIX}/admin/jobs/{pending_job_id}/retry", headers=admin_auth_headers)
    await hit("POST", f"{API_PREFIX}/admin/jobs/prune", headers=admin_auth_headers, json={"statuses": ["finished", "failed", "cancelled"]})
    await hit("POST", f"{API_PREFIX}/admin/jobs/process", headers=admin_auth_headers)

    await hit("GET", f"{API_PREFIX}/admin/logs", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/logs/categories", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/logs/summary", headers=admin_auth_headers)

    await hit("GET", f"{API_PREFIX}/admin/news-categories", headers=admin_auth_headers)
    category_response = await hit(
        "POST",
        f"{API_PREFIX}/admin/news-categories",
        headers=admin_auth_headers,
        json={"name": f"Route Category {unique}", "slug": f"route-category-{unique}"},
    )
    categories_after_create = await async_client.get(f"{API_PREFIX}/admin/news-categories", headers=admin_auth_headers)
    assert categories_after_create.status_code == 200, categories_after_create.text
    category_id = next(item["id"] for item in categories_after_create.json()["data"] if item["slug"] == f"route-category-{unique}")
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/news-categories/{{category_id}}",
        url=f"{API_PREFIX}/admin/news-categories/{category_id}",
        headers=admin_auth_headers,
        json={"name": "Route Category Updated", "slug": f"route-category-updated-{unique}"},
    )

    await hit("GET", f"{API_PREFIX}/admin/tags", headers=admin_auth_headers)
    tag_create = await hit(
        "POST",
        f"{API_PREFIX}/admin/tags",
        headers=admin_auth_headers,
        json={"name": f"Route Tag {unique}", "slug": f"route-tag-{unique}"},
    )
    assert tag_create.json()["success"] is True
    tags_after_create = await async_client.get(f"{API_PREFIX}/admin/tags", headers=admin_auth_headers)
    assert tags_after_create.status_code == 200, tags_after_create.text
    new_tag_id = next(item["id"] for item in tags_after_create.json()["data"] if item["slug"] == f"route-tag-{unique}")
    await hit(
        "PATCH",
        f"{API_PREFIX}/admin/tags/{{tag_id}}",
        url=f"{API_PREFIX}/admin/tags/{new_tag_id}",
        headers=admin_auth_headers,
        json={"name": "Route Tag Updated", "slug": f"route-tag-updated-{unique}"},
    )

    audit_logs = await hit("GET", f"{API_PREFIX}/admin/audit-logs", headers=admin_auth_headers)
    audit_log_id = audit_logs.json()["data"][0]["id"]
    await hit("GET", f"{API_PREFIX}/admin/audit-logs/summary", headers=admin_auth_headers)
    await hit("GET", f"{API_PREFIX}/admin/audit-logs/{{log_id}}", url=f"{API_PREFIX}/admin/audit-logs/{audit_log_id}", headers=admin_auth_headers)

    await hit("DELETE", f"{API_PREFIX}/admin/media/{{media_id}}", url=f"{API_PREFIX}/admin/media/{admin_media_id}", headers=admin_auth_headers)
    await hit("DELETE", f"{API_PREFIX}/admin/tags/{{tag_id}}", url=f"{API_PREFIX}/admin/tags/{new_tag_id}", headers=admin_auth_headers)
    await hit("DELETE", f"{API_PREFIX}/admin/news-categories/{{category_id}}", url=f"{API_PREFIX}/admin/news-categories/{category_id}", headers=admin_auth_headers)
    await hit("DELETE", f"{API_PREFIX}/admin/news/{{news_id}}", url=f"{API_PREFIX}/admin/news/{news_id}", headers=admin_auth_headers)
    await hit("DELETE", f"{API_PREFIX}/admin/matches/{{match_id}}", url=f"{API_PREFIX}/admin/matches/{match_id}", headers=admin_auth_headers)
    await hit("DELETE", f"{API_PREFIX}/admin/tournaments/{{tournament_id}}", url=f"{API_PREFIX}/admin/tournaments/{tournament_id}", headers=admin_auth_headers)
    await hit("DELETE", f"{API_PREFIX}/admin/players/{{player_id}}", url=f"{API_PREFIX}/admin/players/{player_id}", headers=admin_auth_headers)
    await hit("DELETE", f"{API_PREFIX}/admin/users/{{user_id}}", url=f"{API_PREFIX}/admin/users/{temp_user_id}", headers=admin_auth_headers)

    assert maintenance_job_id >= 1
    expected_routes = _http_route_set()
    assert visited == expected_routes, sorted(expected_routes - visited)


def test_live_websocket_route_is_registered_and_reachable(prepared_test_db: str) -> None:
    del prepared_test_db
    assert _ws_route_set() == {f"{API_PREFIX}/live/ws/live"}

    app = create_app()
    with TestClient(app) as client:
        with client.websocket_connect(f"{API_PREFIX}/live/ws/live") as websocket:
            payload = websocket.receive_json()
            assert payload["event"] == "connected"
