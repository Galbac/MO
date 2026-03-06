from fastapi import APIRouter, Depends

from source.api.api_v1.views.admin.audit import router as audit_router
from source.api.api_v1.views.admin.integrations import router as integrations_router
from source.api.api_v1.views.admin.jobs import router as jobs_router
from source.api.api_v1.views.admin.logs import router as logs_router
from source.api.api_v1.views.admin.matches import router as matches_router
from source.api.api_v1.views.admin.maintenance import router as maintenance_router
from source.api.api_v1.views.admin.media import router as media_router
from source.api.api_v1.views.admin.notifications import router as notifications_router
from source.api.api_v1.views.admin.news import router as news_router
from source.api.api_v1.views.admin.players import router as players_router
from source.api.api_v1.views.admin.rankings import router as rankings_router
from source.api.api_v1.views.admin.settings import router as settings_router
from source.api.api_v1.views.admin.taxonomy import router as taxonomy_router
from source.api.api_v1.views.admin.tournaments import router as tournaments_router
from source.api.api_v1.views.admin.users import router as users_router
from source.api.dependencies.auth import require_roles

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(users_router, dependencies=[Depends(require_roles('admin'))])
router.include_router(players_router, dependencies=[Depends(require_roles('admin'))])
router.include_router(tournaments_router, dependencies=[Depends(require_roles('admin'))])
router.include_router(matches_router, dependencies=[Depends(require_roles('admin', 'operator'))])
router.include_router(maintenance_router, dependencies=[Depends(require_roles('admin'))])
router.include_router(media_router, dependencies=[Depends(require_roles('admin', 'editor'))])
router.include_router(notifications_router, dependencies=[Depends(require_roles('admin'))])
router.include_router(news_router, dependencies=[Depends(require_roles('admin', 'editor'))])
router.include_router(rankings_router, dependencies=[Depends(require_roles('admin'))])
router.include_router(settings_router, dependencies=[Depends(require_roles('admin'))])
router.include_router(integrations_router, dependencies=[Depends(require_roles('admin'))])
router.include_router(jobs_router, dependencies=[Depends(require_roles('admin'))])
router.include_router(logs_router, dependencies=[Depends(require_roles('admin'))])
router.include_router(taxonomy_router, dependencies=[Depends(require_roles('admin', 'editor'))])
router.include_router(audit_router, dependencies=[Depends(require_roles('admin'))])
