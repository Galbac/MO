from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from source.services import PortalQueryService

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
query_service = PortalQueryService()


def _seo_defaults(request: Request, page_title: str, description: str | None = None, image_url: str | None = None) -> dict[str, object]:
    canonical_url = str(request.url)
    description_value = description or page_title
    return {
        'canonical_url': canonical_url,
        'meta_description': description_value,
        'og_title': page_title,
        'og_description': description_value,
        'og_type': 'website',
        'og_image': image_url or '',
        'robots': 'index,follow',
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
    robots: str = 'index,follow',
    **extra: object,
):
    context = {
        'request': request,
        'page_title': page_title,
        'page_name': page_name,
        'section': section,
        **_seo_defaults(request, page_title, description=description, image_url=image_url),
        **extra,
    }
    context['robots'] = robots
    return templates.TemplateResponse(request, template_name, context)


@router.get('/robots.txt', include_in_schema=False)
async def robots_txt(request: Request) -> PlainTextResponse:
    sitemap_url = f'{request.base_url}sitemap.xml'
    return PlainTextResponse(f'User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n')


@router.get('/sitemap.xml', include_in_schema=False)
async def sitemap_xml(request: Request) -> Response:
    base_url = str(request.base_url).rstrip('/')
    static_paths = ['/', '/players', '/tournaments', '/matches', '/live', '/rankings', '/news', '/search', '/h2h']
    dynamic_paths: list[str] = []

    players = (await query_service.list_players(None, None, None, None, None, None, 1, 200)).data
    tournaments = (await query_service.list_tournaments(1, 200)).data
    matches = (await query_service.list_matches(1, 200, None)).data
    news = (await query_service.list_news(1, 200)).data

    dynamic_paths.extend([f'/players/{item.slug}' for item in players])
    dynamic_paths.extend([f'/tournaments/{item.slug}' for item in tournaments])
    dynamic_paths.extend([f'/matches/{item.slug}' for item in matches])
    dynamic_paths.extend([f'/news/{item.slug}' for item in news])

    urls = '\n'.join([f'  <url><loc>{base_url}{path}</loc></url>' for path in [*static_paths, *dynamic_paths]])
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n'
    return Response(content=xml, media_type='application/xml')


@router.get('/', include_in_schema=False)
async def home(request: Request):
    return render(request, 'public/index.html', page_title='Tennis Portal', page_name='home', section='public', description='Live scores, rankings, news, players and tournaments from the tennis world.')


@router.get('/players', include_in_schema=False)
async def players_page(request: Request):
    return render(request, 'public/players.html', page_title='Players', page_name='players-list', section='public', description='Browse tennis players, rankings, form, stats and recent matches.')


@router.get('/players/{player_slug}', include_in_schema=False)
async def player_detail_page(request: Request, player_slug: str):
    return render(request, 'public/player-detail.html', page_title=f'Player - {player_slug}', page_name='player-detail', section='public', description=f'Tennis player profile for {player_slug}.', entity_slug=player_slug)


@router.get('/tournaments', include_in_schema=False)
async def tournaments_page(request: Request):
    return render(request, 'public/tournaments.html', page_title='Tournaments', page_name='tournaments-list', section='public', description='Tournament calendar, draws, players and results.')


@router.get('/tournaments/{tournament_slug}', include_in_schema=False)
async def tournament_detail_page(request: Request, tournament_slug: str):
    return render(request, 'public/tournament-detail.html', page_title=f'Tournament - {tournament_slug}', page_name='tournament-detail', section='public', description=f'Tournament page for {tournament_slug}.', entity_slug=tournament_slug)


@router.get('/matches', include_in_schema=False)
async def matches_page(request: Request):
    return render(request, 'public/matches.html', page_title='Matches', page_name='matches-list', section='public', description='Upcoming, live and finished tennis matches with scores and statistics.')


@router.get('/matches/{match_slug}', include_in_schema=False)
async def match_detail_page(request: Request, match_slug: str):
    return render(request, 'public/match-detail.html', page_title=f'Match - {match_slug}', page_name='match-detail', section='public', description=f'Live score, stats and preview for {match_slug}.', entity_slug=match_slug)


@router.get('/live', include_in_schema=False)
async def live_page(request: Request):
    return render(request, 'public/live.html', page_title='Live Center', page_name='live-center', section='public', description='Real-time live scores, feed and ongoing tennis matches.')


@router.get('/rankings', include_in_schema=False)
async def rankings_page(request: Request):
    return render(request, 'public/rankings.html', page_title='Rankings', page_name='rankings', section='public', description='Current tennis rankings, ranking history and movements.')


@router.get('/h2h', include_in_schema=False)
async def h2h_page(request: Request):
    return render(request, 'public/h2h.html', page_title='Head to Head', page_name='h2h', section='public', description='Compare two tennis players and inspect their head-to-head record.')


@router.get('/news', include_in_schema=False)
async def news_page(request: Request):
    return render(request, 'public/news.html', page_title='News', page_name='news-list', section='public', description='Latest tennis news, analysis, live stories and editorial coverage.')


@router.get('/news/{slug}', include_in_schema=False)
async def news_detail_page(request: Request, slug: str):
    return render(request, 'public/news-detail.html', page_title=f'News - {slug}', page_name='news-detail', section='public', description=f'Tennis news article: {slug}.', entity_slug=slug)


@router.get('/search', include_in_schema=False)
async def search_page(request: Request):
    return render(request, 'public/search.html', page_title='Search', page_name='search', section='public', description='Search players, tournaments, matches and news across the portal.')


@router.get('/account', include_in_schema=False)
async def account_page(request: Request):
    return render(request, 'public/account.html', page_title='Account', page_name='account', section='public', description='Personal settings, favorites, subscriptions and notifications.', robots='noindex,nofollow')


@router.get('/notifications', include_in_schema=False)
async def notifications_page(request: Request):
    return render(request, 'public/notifications.html', page_title='Notifications', page_name='notifications', section='public', description='Recent notification history and unread alerts.', robots='noindex,nofollow')


@router.get('/404', include_in_schema=False)
async def not_found_page(request: Request):
    return render(request, 'public/404.html', page_title='404', page_name='404', section='public', description='Page not found.', robots='noindex,nofollow')


@router.get('/500', include_in_schema=False)
async def server_error_page(request: Request):
    return render(request, 'public/500.html', page_title='500', page_name='500', section='public', description='Internal server error page.', robots='noindex,nofollow')


@router.get('/admin', include_in_schema=False)
async def admin_dashboard_page(request: Request):
    return render(request, 'admin/dashboard.html', page_title='Admin Dashboard', page_name='admin-dashboard', section='admin', robots='noindex,nofollow')


@router.get('/admin/login', include_in_schema=False)
async def admin_login_page(request: Request):
    return render(request, 'admin/login.html', page_title='Admin Login', page_name='admin-login', section='admin', robots='noindex,nofollow')


@router.get('/admin/users', include_in_schema=False)
async def admin_users_page(request: Request):
    return render(request, 'admin/users.html', page_title='Admin Users', page_name='admin-users', section='admin', robots='noindex,nofollow')


@router.get('/admin/users/{user_id}', include_in_schema=False)
async def admin_user_detail_page(request: Request, user_id: int):
    return render(request, 'admin/user-detail.html', page_title=f'Admin User {user_id}', page_name='admin-user-detail', section='admin', robots='noindex,nofollow', entity_id=user_id)


@router.get('/admin/players', include_in_schema=False)
async def admin_players_page(request: Request):
    return render(request, 'admin/players.html', page_title='Admin Players', page_name='admin-players', section='admin', robots='noindex,nofollow')


@router.get('/admin/players/new', include_in_schema=False)
async def admin_player_create_page(request: Request):
    return render(request, 'admin/player-form.html', page_title='Create Player', page_name='admin-player-form', section='admin', robots='noindex,nofollow')


@router.get('/admin/tournaments', include_in_schema=False)
async def admin_tournaments_page(request: Request):
    return render(request, 'admin/tournaments.html', page_title='Admin Tournaments', page_name='admin-tournaments', section='admin', robots='noindex,nofollow')


@router.get('/admin/tournaments/new', include_in_schema=False)
async def admin_tournament_create_page(request: Request):
    return render(request, 'admin/tournament-form.html', page_title='Create Tournament', page_name='admin-tournament-form', section='admin', robots='noindex,nofollow')


@router.get('/admin/matches', include_in_schema=False)
async def admin_matches_page(request: Request):
    return render(request, 'admin/matches.html', page_title='Admin Matches', page_name='admin-matches', section='admin', robots='noindex,nofollow')


@router.get('/admin/matches/{match_id}', include_in_schema=False)
async def admin_match_detail_page(request: Request, match_id: int):
    return render(request, 'admin/match-detail.html', page_title=f'Admin Match {match_id}', page_name='admin-match-detail', section='admin', robots='noindex,nofollow', entity_id=match_id)


@router.get('/admin/live-operations', include_in_schema=False)
async def admin_live_operations_page(request: Request):
    return render(request, 'admin/live-operations.html', page_title='Live Operations', page_name='admin-live-operations', section='admin', robots='noindex,nofollow')


@router.get('/admin/rankings', include_in_schema=False)
async def admin_rankings_page(request: Request):
    return render(request, 'admin/rankings.html', page_title='Admin Rankings', page_name='admin-rankings', section='admin', robots='noindex,nofollow')


@router.get('/admin/news', include_in_schema=False)
async def admin_news_page(request: Request):
    return render(request, 'admin/news.html', page_title='Admin News', page_name='admin-news', section='admin', robots='noindex,nofollow')


@router.get('/admin/news/new', include_in_schema=False)
async def admin_news_form_page(request: Request):
    return render(request, 'admin/news-form.html', page_title='Create News', page_name='admin-news-form', section='admin', robots='noindex,nofollow')


@router.get('/admin/categories', include_in_schema=False)
async def admin_categories_page(request: Request):
    return render(request, 'admin/categories.html', page_title='Admin Categories', page_name='admin-categories', section='admin', robots='noindex,nofollow')


@router.get('/admin/tags', include_in_schema=False)
async def admin_tags_page(request: Request):
    return render(request, 'admin/tags.html', page_title='Admin Tags', page_name='admin-tags', section='admin', robots='noindex,nofollow')


@router.get('/admin/media', include_in_schema=False)
async def admin_media_page(request: Request):
    return render(request, 'admin/media.html', page_title='Admin Media', page_name='admin-media', section='admin', robots='noindex,nofollow')


@router.get('/admin/notifications', include_in_schema=False)
async def admin_notifications_page(request: Request):
    return render(request, 'admin/notifications.html', page_title='Admin Notifications', page_name='admin-notifications', section='admin', robots='noindex,nofollow')


@router.get('/admin/integrations', include_in_schema=False)
async def admin_integrations_page(request: Request):
    return render(request, 'admin/integrations.html', page_title='Admin Integrations', page_name='admin-integrations', section='admin', robots='noindex,nofollow')


@router.get('/admin/audit', include_in_schema=False)
async def admin_audit_page(request: Request):
    return render(request, 'admin/audit.html', page_title='Admin Audit', page_name='admin-audit', section='admin', robots='noindex,nofollow')


@router.get('/admin/settings', include_in_schema=False)
async def admin_settings_page(request: Request):
    return render(request, 'admin/settings.html', page_title='Admin Settings', page_name='admin-settings', section='admin', robots='noindex,nofollow')
