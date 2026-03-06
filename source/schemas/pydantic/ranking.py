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


class RankingImportJob(BaseModel):
    id: int
    ranking_type: str
    status: str
    imported_at: str
    processed_rows: int
