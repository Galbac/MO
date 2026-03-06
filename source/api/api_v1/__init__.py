from fastapi import APIRouter

from source.api.api_v1.views.auth import router as auth_router
from source.api.api_v1.views.healthz import router as health_router
from source.api.api_v1.views.live import router as live_router
from source.api.api_v1.views.matches import router as matches_router
from source.api.api_v1.views.media import router as media_router
from source.api.api_v1.views.news import router as news_router
from source.api.api_v1.views.notifications import router as notifications_router
from source.api.api_v1.views.players import router as players_router
from source.api.api_v1.views.rankings import router as rankings_router
from source.api.api_v1.views.search import router as search_router
from source.api.api_v1.views.tournaments import router as tournaments_router
from source.api.api_v1.views.users import router as users_router
from source.api.api_v1.views.admin import router as admin_router
from source.config.settings import settings

public_router = APIRouter(prefix=settings.api.v1.prefix)
public_router.include_router(health_router)
public_router.include_router(auth_router)
public_router.include_router(users_router)
public_router.include_router(players_router)
public_router.include_router(tournaments_router)
public_router.include_router(matches_router)
public_router.include_router(live_router)
public_router.include_router(rankings_router)
public_router.include_router(news_router)
public_router.include_router(search_router)
public_router.include_router(notifications_router)
public_router.include_router(media_router)
public_router.include_router(admin_router)
