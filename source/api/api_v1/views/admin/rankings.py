from fastapi import APIRouter

from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.ranking import RankingImportJob, RankingImportResult, RankingRecalculationResult
from source.services import AdminSupportService

router = APIRouter(prefix="/rankings", tags=["admin-rankings"])
service = AdminSupportService()


@router.get("/import-jobs", response_model=SuccessResponse[list[RankingImportJob]])
async def get_admin_ranking_jobs() -> SuccessResponse[list[RankingImportJob]]:
    return await service.list_ranking_jobs()


@router.post("/import", response_model=SuccessResponse[RankingImportResult])
async def import_admin_rankings(payload: dict | None = None) -> SuccessResponse[RankingImportResult]:
    return await service.import_rankings(payload or {})


@router.post("/recalculate-movements", response_model=SuccessResponse[RankingRecalculationResult])
async def recalculate_admin_ranking_movements() -> SuccessResponse[RankingRecalculationResult]:
    return await service.recalculate_ranking_movements()
