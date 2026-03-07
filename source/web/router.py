import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from source.config.settings import settings
from source.services import PortalQueryService

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
query_service = PortalQueryService()
ADMIN_SETTINGS_FILE = Path("var/admin_settings.json")


def _absolute_url(request: Request, value: str | None) -> str:
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"{_site_base_url(request)}/{value.lstrip('/')}"


def _site_base_url(request: Request) -> str:
    configured = settings.site.base_url.rstrip('/')
    if configured:
        return configured
    return str(request.base_url).rstrip('/')


def _seo_defaults(
    request: Request,
    page_title: str,
    description: str | None = None,
    image_url: str | None = None,
    *,
    og_type: str = "website",
) -> dict[str, object]:
    canonical_url = f"{_site_base_url(request)}{request.url.path}"
    if request.url.query:
        canonical_url = f"{canonical_url}?{request.url.query}"
    description_value = description or page_title
    return {
        "canonical_url": canonical_url,
        "meta_description": description_value,
        "og_title": page_title,
        "og_description": description_value,
        "og_type": og_type,
        "og_image": _absolute_url(request, image_url),
        "robots": "index,follow",
        "schema_json": "",
    }


def _ui_settings() -> dict[str, object]:
    defaults = {
        "ui_mode": "current",
        "evening_theme_enabled": False,
    }
    if not ADMIN_SETTINGS_FILE.exists():
        return defaults
    try:
        payload = json.loads(ADMIN_SETTINGS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return defaults
    return {
        "ui_mode": payload.get("ui_mode", "current") if payload.get("ui_mode") in {"current", "future_3000"} else "current",
        "evening_theme_enabled": bool(payload.get("evening_theme_enabled", False)),
    }


def render(
    request: Request,
    template_name: str,
    *,
    page_title: str,
    page_name: str,
    section: str,
    description: str | None = None,
    image_url: str | None = None,
    robots: str = "index,follow",
    og_type: str = "website",
    schema_json: dict | list | None = None,
    **extra: object,
):
    context = {
        "request": request,
        "page_title": page_title,
        "page_name": page_name,
        "section": section,
        "dev_reload": settings.run.dev_reload,
        **_ui_settings(),
        **_seo_defaults(request, page_title, description=description, image_url=image_url, og_type=og_type),
        **extra,
    }
    context["robots"] = robots
    context["schema_json"] = json.dumps(schema_json, ensure_ascii=False) if schema_json else ""
    return templates.TemplateResponse(request, template_name, context)


async def _player_context(request: Request, player_slug: str) -> dict[str, object]:
    players = (await query_service.list_players(None, None, None, None, None, None, 1, 300)).data
    player = next((item for item in players if item.slug == player_slug), None)
    if player is None:
        return {"entity_slug": player_slug}
    detail = (await query_service.get_player(player.id)).data
    page_title = detail.seo.title if detail.seo and detail.seo.title else detail.full_name
    description = detail.seo.description if detail.seo and detail.seo.description else (detail.biography or detail.full_name)
    return {
        "page_title": page_title,
        "description": description,
        "image_url": detail.photo_url,
        "schema_json": {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": detail.full_name,
            "description": detail.biography or detail.full_name,
            "image": _absolute_url(request, detail.photo_url),
            "nationality": detail.country_name or detail.country_code,
            "url": str(request.url),
        },
        "entity_slug": player_slug,
    }


async def _tournament_context(request: Request, tournament_slug: str) -> dict[str, object]:
    tournaments = (await query_service.list_tournaments(1, 300)).data
    tournament = next((item for item in tournaments if item.slug == tournament_slug), None)
    if tournament is None:
        return {"entity_slug": tournament_slug}
    detail = (await query_service.get_tournament(tournament.id)).data
    description = detail.description or detail.name
    return {
        "page_title": detail.name,
        "description": description,
        "image_url": detail.logo_url,
        "schema_json": {
            "@context": "https://schema.org",
            "@type": "SportsEvent",
            "name": detail.name,
            "description": description,
            "startDate": detail.start_date,
            "endDate": detail.end_date,
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {
                "@type": "Place",
                "name": detail.city or detail.name,
                "address": detail.country_code or "",
            },
            "image": _absolute_url(request, detail.logo_url),
            "url": str(request.url),
        },
        "entity_slug": tournament_slug,
    }


async def _match_context(request: Request, match_slug: str) -> dict[str, object]:
    matches = (await query_service.list_matches(1, 300, None)).data
    match = next((item for item in matches if item.slug == match_slug), None)
    if match is None:
        return {"entity_slug": match_slug}
    detail = (await query_service.get_match(match.id)).data
    title = f"{detail.player1_name} vs {detail.player2_name}"
    description = f"{detail.tournament_name}, {detail.round_code or detail.status}. Счет: {detail.score.current_game or detail.score_summary or detail.status}."
    return {
        "page_title": title,
        "description": description,
        "schema_json": {
            "@context": "https://schema.org",
            "@type": "SportsEvent",
            "name": title,
            "description": description,
            "startDate": detail.scheduled_at.isoformat(),
            "competitor": [
                {"@type": "Person", "name": detail.player1_name},
                {"@type": "Person", "name": detail.player2_name},
            ],
            "eventStatus": detail.status,
            "location": {"@type": "Place", "name": detail.court_name or detail.tournament_name},
            "url": str(request.url),
        },
        "entity_slug": match_slug,
    }


async def _news_context(request: Request, slug: str) -> dict[str, object]:
    article = (await query_service.get_news_article(slug)).data
    page_title = article.seo_title or article.title
    description = article.seo_description or article.lead or article.subtitle or article.title
    return {
        "page_title": page_title,
        "description": description,
        "image_url": article.cover_image_url,
        "og_type": "article",
        "schema_json": {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": article.title,
            "description": description,
            "datePublished": article.published_at,
            "image": _absolute_url(request, article.cover_image_url),
            "url": f"{_site_base_url(request)}{request.url.path}",
            "author": {"@type": "Person", "name": settings.site.editorial_name},
        },
        "entity_slug": slug,
    }


@router.get("/robots.txt", include_in_schema=False)
async def robots_txt(request: Request) -> PlainTextResponse:
    sitemap_url = f"{_site_base_url(request)}/sitemap.xml"
    return PlainTextResponse(f"User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n")


@router.get("/__dev__/reload-token", include_in_schema=False)
async def dev_reload_token() -> Response:
    if not settings.run.dev_reload:
        return Response(content=json.dumps({"enabled": False}), media_type="application/json")

    watched_roots = [
        Path("source/web/templates"),
        Path("source/web/static"),
        Path("source"),
        Path("docker"),
    ]
    latest_mtime = 0.0
    for root in watched_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                latest_mtime = max(latest_mtime, path.stat().st_mtime)
            except OSError:
                continue

    payload = {
        "enabled": True,
        "token": latest_mtime,
        "updated_at": datetime.fromtimestamp(latest_mtime, tz=UTC).isoformat() if latest_mtime else None,
    }
    return Response(content=json.dumps(payload), media_type="application/json")


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml(request: Request) -> Response:
    base_url = _site_base_url(request)
    static_paths = ["/portal", "/players", "/tournaments", "/matches", "/live", "/rankings", "/news", "/search", "/h2h"]
    dynamic_paths: list[str] = []

    players = (await query_service.list_players(None, None, None, None, None, None, 1, 200)).data
    tournaments = (await query_service.list_tournaments(1, 200)).data
    matches = (await query_service.list_matches(1, 200, None)).data
    news = (await query_service.list_news(1, 200)).data

    dynamic_paths.extend([f"/players/{item.slug}" for item in players])
    dynamic_paths.extend([f"/tournaments/{item.slug}" for item in tournaments])
    dynamic_paths.extend([f"/matches/{item.slug}" for item in matches])
    dynamic_paths.extend([f"/news/{item.slug}" for item in news])

    urls = "\n".join([f"  <url><loc>{base_url}{path}</loc></url>" for path in [*static_paths, *dynamic_paths]])
    xml = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n{urls}\n</urlset>\n"
    return Response(content=xml, media_type="application/xml")


@router.get("/", include_in_schema=False)
async def home(request: Request):
    return render(request, "public/register.html", page_title="Регистрация", page_name="register", section="public", description="Регистрация в Makhachkala Open с согласием на обработку персональных данных.", robots="noindex,nofollow")


@router.get("/register", include_in_schema=False)
async def register_page(request: Request):
    return render(request, "public/register.html", page_title="Регистрация", page_name="register", section="public", description="Регистрация в Makhachkala Open с согласием на обработку персональных данных.", robots="noindex,nofollow")


@router.get("/portal", include_in_schema=False)
async def portal_page(request: Request):
    return render(request, "public/index.html", page_title=settings.names.title, page_name="home", section="public", description="Лайв-счета, рейтинги, новости, игроки и турниры Makhachkala Open.", schema_json={"@context": "https://schema.org", "@type": "WebSite", "name": settings.names.title, "url": _site_base_url(request)})


@router.get("/players", include_in_schema=False)
async def players_page(request: Request):
    return render(request, "public/players.html", page_title="Игроки", page_name="players-list", section="public", description="Игроки, рейтинг, форма, статистика и последние матчи.")


@router.get("/players/{player_slug}", include_in_schema=False)
async def player_detail_page(request: Request, player_slug: str):
    context = await _player_context(request, player_slug)
    return render(request, "public/player-detail.html", page_title=str(context.pop("page_title", f"Игрок - {player_slug}")), page_name="player-detail", section="public", **context)


@router.get("/tournaments", include_in_schema=False)
async def tournaments_page(request: Request):
    return render(request, "public/tournaments.html", page_title="Турниры", page_name="tournaments-list", section="public", description="Календарь турниров, сетки, игроки и результаты.")


@router.get("/tournaments/{tournament_slug}", include_in_schema=False)
async def tournament_detail_page(request: Request, tournament_slug: str):
    context = await _tournament_context(request, tournament_slug)
    return render(request, "public/tournament-detail.html", page_title=str(context.pop("page_title", f"Турнир - {tournament_slug}")), page_name="tournament-detail", section="public", **context)


@router.get("/matches", include_in_schema=False)
async def matches_page(request: Request):
    return render(request, "public/matches.html", page_title="Матчи", page_name="matches-list", section="public", description="Предстоящие, лайв и завершенные матчи со счетом и статистикой.")


@router.get("/matches/{match_slug}", include_in_schema=False)
async def match_detail_page(request: Request, match_slug: str):
    context = await _match_context(request, match_slug)
    return render(request, "public/match-detail.html", page_title=str(context.pop("page_title", f"Матч - {match_slug}")), page_name="match-detail", section="public", **context)


@router.get("/live", include_in_schema=False)
async def live_page(request: Request):
    return render(request, "public/live.html", page_title="Лайв-центр", page_name="live-center", section="public", description="Матчи, лента событий и счет в реальном времени.")


@router.get("/rankings", include_in_schema=False)
async def rankings_page(request: Request):
    return render(request, "public/rankings.html", page_title="Рейтинги", page_name="rankings", section="public", description="Актуальные рейтинги, история позиций и движения.")


@router.get("/h2h", include_in_schema=False)
async def h2h_page(request: Request):
    return render(request, "public/h2h.html", page_title="Личные встречи", page_name="h2h", section="public", description="Сравнение двух игроков и история их личных встреч.")


@router.get("/news", include_in_schema=False)
async def news_page(request: Request):
    return render(request, "public/news.html", page_title="Новости", page_name="news-list", section="public", description="Последние новости, аналитика и редакционные материалы.")


@router.get("/news/{slug}", include_in_schema=False)
async def news_detail_page(request: Request, slug: str):
    context = await _news_context(request, slug)
    return render(request, "public/news-detail.html", page_title=str(context.pop("page_title", f"Новость - {slug}")), page_name="news-detail", section="public", **context)


@router.get("/search", include_in_schema=False)
async def search_page(request: Request):
    return render(request, "public/search.html", page_title="Поиск", page_name="search", section="public", description="Поиск по игрокам, турнирам, матчам и новостям.")


@router.get("/account", include_in_schema=False)
async def account_page(request: Request):
    return render(request, "public/account.html", page_title="Профиль", page_name="account", section="public", description="Личные настройки, избранное, подписки и уведомления.", robots="noindex,nofollow")


@router.get("/notifications", include_in_schema=False)
async def notifications_page(request: Request):
    return render(request, "public/notifications.html", page_title="Уведомления", page_name="notifications", section="public", description="История уведомлений и непрочитанные события.", robots="noindex,nofollow")


@router.get("/404", include_in_schema=False)
async def not_found_page(request: Request):
    return render(request, "public/404.html", page_title="404", page_name="404", section="public", description="Страница не найдена.", robots="noindex,nofollow")


@router.get("/500", include_in_schema=False)
async def server_error_page(request: Request):
    return render(request, "public/500.html", page_title="500", page_name="500", section="public", description="Страница внутренней ошибки сервера.", robots="noindex,nofollow")


@router.get("/admin", include_in_schema=False)
async def admin_dashboard_page(request: Request):
    return render(request, "admin/dashboard.html", page_title="Админка - Панель", page_name="admin-dashboard", section="admin", robots="noindex,nofollow")


@router.get("/admin/login", include_in_schema=False)
async def admin_login_page(request: Request):
    return render(request, "admin/login.html", page_title="Админка - Вход", page_name="admin-login", section="admin", robots="noindex,nofollow")


@router.get("/admin/users", include_in_schema=False)
async def admin_users_page(request: Request):
    return render(request, "admin/users.html", page_title="Админка - Пользователи", page_name="admin-users", section="admin", robots="noindex,nofollow")


@router.get("/admin/users/{user_id}", include_in_schema=False)
async def admin_user_detail_page(request: Request, user_id: int):
    return render(request, "admin/user-detail.html", page_title=f"Админка - Пользователь {user_id}", page_name="admin-user-detail", section="admin", robots="noindex,nofollow", entity_id=user_id)


@router.get("/admin/players", include_in_schema=False)
async def admin_players_page(request: Request):
    return render(request, "admin/players.html", page_title="Админка - Игроки", page_name="admin-players", section="admin", robots="noindex,nofollow")


@router.get("/admin/players/new", include_in_schema=False)
async def admin_player_create_page(request: Request):
    return render(request, "admin/player-form.html", page_title="Админка - Новый игрок", page_name="admin-player-form", section="admin", robots="noindex,nofollow")


@router.get("/admin/tournaments", include_in_schema=False)
async def admin_tournaments_page(request: Request):
    return render(request, "admin/tournaments.html", page_title="Админка - Турниры", page_name="admin-tournaments", section="admin", robots="noindex,nofollow")


@router.get("/admin/tournaments/new", include_in_schema=False)
async def admin_tournament_create_page(request: Request):
    return render(request, "admin/tournament-form.html", page_title="Админка - Новый турнир", page_name="admin-tournament-form", section="admin", robots="noindex,nofollow")


@router.get("/admin/matches", include_in_schema=False)
async def admin_matches_page(request: Request):
    return render(request, "admin/matches.html", page_title="Админка - Матчи", page_name="admin-matches", section="admin", robots="noindex,nofollow")


@router.get("/admin/matches/{match_id}", include_in_schema=False)
async def admin_match_detail_page(request: Request, match_id: int):
    return render(request, "admin/match-detail.html", page_title=f"Админка - Матч {match_id}", page_name="admin-match-detail", section="admin", robots="noindex,nofollow", entity_id=match_id)


@router.get("/admin/live-operations", include_in_schema=False)
async def admin_live_operations_page(request: Request):
    return render(request, "admin/live-operations.html", page_title="Админка - Лайв-операции", page_name="admin-live-operations", section="admin", robots="noindex,nofollow")


@router.get("/admin/rankings", include_in_schema=False)
async def admin_rankings_page(request: Request):
    return render(request, "admin/rankings.html", page_title="Админка - Рейтинги", page_name="admin-rankings", section="admin", robots="noindex,nofollow")


@router.get("/admin/news", include_in_schema=False)
async def admin_news_page(request: Request):
    return render(request, "admin/news.html", page_title="Админка - Новости", page_name="admin-news", section="admin", robots="noindex,nofollow")


@router.get("/admin/news/new", include_in_schema=False)
async def admin_news_form_page(request: Request):
    return render(request, "admin/news-form.html", page_title="Админка - Новая новость", page_name="admin-news-form", section="admin", robots="noindex,nofollow")


@router.get("/admin/categories", include_in_schema=False)
async def admin_categories_page(request: Request):
    return render(request, "admin/categories.html", page_title="Админка - Категории", page_name="admin-categories", section="admin", robots="noindex,nofollow")


@router.get("/admin/tags", include_in_schema=False)
async def admin_tags_page(request: Request):
    return render(request, "admin/tags.html", page_title="Админка - Теги", page_name="admin-tags", section="admin", robots="noindex,nofollow")


@router.get("/admin/media", include_in_schema=False)
async def admin_media_page(request: Request):
    return render(request, "admin/media.html", page_title="Админка - Медиа", page_name="admin-media", section="admin", robots="noindex,nofollow")


@router.get("/admin/notifications", include_in_schema=False)
async def admin_notifications_page(request: Request):
    return render(request, "admin/notifications.html", page_title="Админка - Уведомления", page_name="admin-notifications", section="admin", robots="noindex,nofollow")


@router.get("/admin/integrations", include_in_schema=False)
async def admin_integrations_page(request: Request):
    return render(request, "admin/integrations.html", page_title="Админка - Интеграции", page_name="admin-integrations", section="admin", robots="noindex,nofollow")


@router.get("/admin/jobs", include_in_schema=False)
async def admin_jobs_page(request: Request):
    return render(request, "admin/jobs.html", page_title="Админка - Очередь задач", page_name="admin-jobs", section="admin", robots="noindex,nofollow")


@router.get("/admin/logs", include_in_schema=False)
async def admin_logs_page(request: Request):
    return render(request, "admin/logs.html", page_title="Админка - Логи", page_name="admin-logs", section="admin", robots="noindex,nofollow")


@router.get("/admin/maintenance", include_in_schema=False)
async def admin_maintenance_page(request: Request):
    return render(request, "admin/maintenance.html", page_title="Админка - Maintenance", page_name="admin-maintenance", section="admin", robots="noindex,nofollow")


@router.get("/admin/audit", include_in_schema=False)
async def admin_audit_page(request: Request):
    return render(request, "admin/audit.html", page_title="Админка - Аудит", page_name="admin-audit", section="admin", robots="noindex,nofollow")


@router.get("/admin/settings", include_in_schema=False)
async def admin_settings_page(request: Request):
    return render(request, "admin/settings.html", page_title="Админка - Настройки", page_name="admin-settings", section="admin", robots="noindex,nofollow")
