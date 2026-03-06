from pydantic import BaseModel, Field


class TournamentSummary(BaseModel):
    id: int
    slug: str
    name: str
    category: str
    surface: str
    season_year: int
    start_date: str | None = None
    end_date: str | None = None
    status: str = "scheduled"
    city: str | None = None
    live_matches_count: int = 0
    participants_count: int = 0


class ChampionItem(BaseModel):
    season_year: int
    player_id: int | None = None
    player_name: str
    tournament_id: int | None = None
    tournament_name: str | None = None
    surface: str | None = None
    category: str | None = None


class DrawMatchItem(BaseModel):
    match_id: int | None = None
    slug: str | None = None
    round_code: str
    player1_name: str
    player2_name: str
    status: str | None = None
    scheduled_at: str | None = None
    court_name: str | None = None
    winner_id: int | None = None
    score_summary: str | None = None


class TournamentDetail(TournamentSummary):
    short_name: str | None = None
    indoor: bool = False
    country_code: str
    prize_money: str | None = None
    points_winner: int | None = None
    logo_url: str | None = None
    description: str | None = None
    participants: list[dict] = Field(default_factory=list)
    current_matches: list[dict] = Field(default_factory=list)
    champions: list[ChampionItem] = Field(default_factory=list)
    draw: list[DrawMatchItem] = Field(default_factory=list)
    seo: dict = Field(default_factory=dict)
