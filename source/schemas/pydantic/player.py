from datetime import date

from pydantic import BaseModel, Field


class PlayerListQuery(BaseModel):
    search: str | None = None
    country_code: str | None = None
    hand: str | None = None
    status: str | None = None
    rank_from: int | None = None
    rank_to: int | None = None
    page: int = 1
    per_page: int = 20
    sort: str = "rank_asc"


class PlayerSummary(BaseModel):
    id: int
    slug: str
    full_name: str
    country_code: str
    current_rank: int | None = None
    current_points: int | None = None
    photo_url: str | None = None
    form: list[str] = Field(default_factory=list)


class PlayerStats(BaseModel):
    season: int
    matches_played: int
    wins: int
    losses: int
    win_rate: float
    hard_record: str
    clay_record: str
    grass_record: str
    titles: int = 0
    finals: int = 0
    current_streak: int = 0


class RankingHistoryPoint(BaseModel):
    ranking_type: str | None = None
    ranking_date: str
    rank_position: int
    points: int
    movement: int


class TitleItem(BaseModel):
    tournament_name: str
    season_year: int
    surface: str
    category: str


class SeoMeta(BaseModel):
    title: str
    description: str
    canonical_url: str | None = None


class PlayerNewsItem(BaseModel):
    id: int
    slug: str
    title: str
    published_at: str | None = None
    relevance_score: int = 0
    category_name: str | None = None


class UpcomingMatchItem(BaseModel):
    match_id: int
    slug: str
    tournament_name: str
    opponent_name: str
    scheduled_at: str
    status: str


class PlayerDetail(PlayerSummary):
    first_name: str | None = None
    last_name: str | None = None
    country_name: str | None = None
    birth_date: date | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    hand: str | None = None
    backhand: str | None = None
    biography: str | None = None
    status: str = "active"
    stats: PlayerStats | None = None
    recent_matches: list[dict] = Field(default_factory=list)
    upcoming_match: UpcomingMatchItem | None = None
    ranking_history: list[RankingHistoryPoint] = Field(default_factory=list)
    titles: list[TitleItem] = Field(default_factory=list)
    seo: SeoMeta | None = None


class PlayerComparison(BaseModel):
    player1: PlayerDetail
    player2: PlayerDetail
    h2h: dict
    comparison: dict


class H2HSurfaceSplitItem(BaseModel):
    surface: str
    player1_wins: int
    player2_wins: int


class H2HMatchItem(BaseModel):
    match_id: int
    tournament_id: int | None = None
    tournament_name: str
    tournament_slug: str | None = None
    surface: str | None = None
    season_year: int | None = None
    winner_id: int | None = None
    score_summary: str | None = None
    scheduled_at: str | None = None


class H2HResponse(BaseModel):
    player1_id: int
    player2_id: int
    total_matches: int
    player1_wins: int
    player2_wins: int
    hard_player1_wins: int
    hard_player2_wins: int
    clay_player1_wins: int
    clay_player2_wins: int
    grass_player1_wins: int
    grass_player2_wins: int
    last_match_id: int | None = None
    surface_split: list[H2HSurfaceSplitItem] = Field(default_factory=list)
    matches: list[H2HMatchItem] = Field(default_factory=list)
