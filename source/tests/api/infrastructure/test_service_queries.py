from __future__ import annotations

from starlette.requests import Request

from source.config.settings import settings
from source.schemas.pydantic.auth import ForgotPasswordRequest, ResetPasswordRequest, VerifyEmailRequest
from source.schemas.pydantic.user import UserPasswordChangeRequest, UserUpdateRequest
from source.services.auth_user_service import AuthUserService
from source.services.portal_query_service import PortalQueryService


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


async def test_portal_query_service_smoke(async_client) -> None:
    service = PortalQueryService()

    players = await service.list_players(search=None, country_code=None, hand=None, status=None, rank_from=None, rank_to=None, page=1, per_page=10)
    assert players.data

    player = await service.get_player(1)
    assert player.data.full_name
    assert (await service.get_player_stats(1)).data.matches_played >= 0
    assert (await service.get_player_matches(1, 1, 10)).data
    assert (await service.get_player_ranking_history(1)).data
    assert isinstance((await service.get_player_titles(1)).data, list)
    assert isinstance((await service.get_player_news(1)).data, list)
    assert isinstance((await service.get_player_upcoming_matches(1)).data, list)
    assert (await service.get_h2h(1, 2)).data.total_matches >= 0
    assert (await service.compare_players(1, 2)).data.player1.id == 1

    tournaments = await service.list_tournaments(1, 10)
    assert tournaments.data
    tournament = await service.get_tournament(1)
    assert tournament.data.name
    assert isinstance((await service.get_tournament_matches(1)).data, list)
    assert isinstance((await service.get_tournament_draw(1)).data, list)
    assert isinstance((await service.get_tournament_players(1)).data, list)
    assert isinstance((await service.get_tournament_champions(1)).data, list)
    assert isinstance((await service.get_tournament_news(1)).data, list)
    assert (await service.get_tournament_calendar()).data

    matches = await service.list_matches(page=1, per_page=10, status=None)
    assert matches.data
    match = await service.get_match(2)
    assert match.data.slug
    assert (await service.get_match_score(2)).data.sets
    assert (await service.get_match_stats(2)).data is not None
    assert isinstance((await service.get_match_timeline(2)).data, list)
    assert (await service.get_match_h2h(2)).data.total_matches >= 0
    assert (await service.get_match_preview(2)).data.notes
    assert isinstance((await service.get_match_point_by_point(2)).data, list)
    assert (await service.get_upcoming_matches()).data
    assert (await service.get_match_results()).data

    news = await service.list_news(1, 10)
    assert news.data
    assert (await service.get_news_categories()).data
    assert (await service.get_news_tags()).data
    assert (await service.get_featured_news()).data
    assert isinstance((await service.get_related_news('djokovic-wins-ao-2026')).data, list)
    article = await service.get_news_article('djokovic-wins-ao-2026')
    assert article.data.title
    assert isinstance(article.data.related_news, list)


async def test_auth_user_service_direct_methods(async_client, admin_auth_headers, user_auth_headers) -> None:
    service = AuthUserService()
    user_request = _request_with_headers(user_auth_headers)

    me = await service.auth_me(user_request)
    assert me.data.username == 'demo_user'
    assert (await service.users_me(user_request)).data.id == me.data.id

    updated = await service.update_me(user_request, UserUpdateRequest(first_name='Demo', timezone='UTC'))
    assert updated.data.first_name == 'Demo'
    assert updated.data.timezone == 'UTC'

    changed = await service.change_password(
        user_request,
        UserPasswordChangeRequest(current_password='UserPass123', new_password='UserPass456'),
    )
    assert changed.data.message == 'Password changed and tokens revoked'

    forgot = await service.forgot_password(None, ForgotPasswordRequest(email=settings.demo.user_email))
    assert 'reset instructions' in forgot.data.message

    reset_token = service._issue_action_token(user_id=2, purpose='password_reset', ttl_minutes=settings.auth.password_reset_token_ttl_minutes)
    reset = await service.reset_password(ResetPasswordRequest(token=reset_token, new_password='StrongPass123'))
    assert reset.data.message == 'Password reset completed'

    verify_token = service._issue_action_token(user_id=2, purpose='verify_email', ttl_minutes=settings.auth.email_verification_token_ttl_minutes)
    verify = await service.verify_email(VerifyEmailRequest(token=verify_token))
    assert verify.data.message == 'Email verified'

    users = await service.list_admin_users()
    assert users.data
    admin_user = await service.get_admin_user(1)
    assert admin_user.data.username == 'admin'
    admin_updated = await service.update_admin_user(1, {'first_name': 'Root', 'timezone': 'UTC'}, actor_id=1)
    assert admin_updated.data.id == 1

    relogin = await async_client.post('/api/v1/auth/login', json={'email_or_username': 'demo_user', 'password': 'StrongPass123'})
    assert relogin.status_code == 200
