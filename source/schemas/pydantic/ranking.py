from datetime import date

from pydantic import BaseModel, Field


class RankingEntry(BaseModel):
    position: int
    player_id: int | None = None
    player_name: str
    country_code: str
    points: int
    movement: int
    ranking_type: str = "atp"
    ranking_date: str = Field(default_factory=lambda: date.today().isoformat())


class RankingSnapshotItem(BaseModel):
    ranking_type: str
    ranking_date: str
    entries: list[RankingEntry]
    total_entries: int = 0


class PlayerRankingRecord(BaseModel):
    ranking_type: str
    ranking_date: str
    position: int
    points: int
    movement: int


class RankingImportJob(BaseModel):
    id: int
    ranking_type: str
    status: str
    imported_at: str
    processed_rows: int


class RankingImportResult(BaseModel):
    ranking_type: str
    status: str
    imported_at: str
    processed_rows: int
    source: str | None = None
    mode: str
    message: str | None = None


class RankingRecalculationResult(BaseModel):
    message: str = 'Ranking movements recalculated'
    ranking_types: list[str]
    snapshot_dates_processed: int
    updated_rows: int
