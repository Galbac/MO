from datetime import datetime

from pydantic import BaseModel, Field

from source.schemas.pydantic.news import NewsArticleSummary


class MatchSummary(BaseModel):
    id: int
    slug: str
    status: str
    scheduled_at: datetime
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    player1_id: int | None = None
    player2_id: int | None = None
    player1_name: str
    player2_name: str
    tournament_id: int | None = None
    tournament_name: str
    round_code: str | None = None
    court_name: str | None = None
    score_summary: str | None = None


class MatchScore(BaseModel):
    sets: list[str] = Field(default_factory=list)
    current_game: str | None = None
    serving_player_id: int | None = None
    winner_id: int | None = None
    status: str | None = None
    completed_sets: int = 0


class MatchSetItem(BaseModel):
    set_number: int
    player1_games: int
    player2_games: int
    tiebreak_player1_points: int | None = None
    tiebreak_player2_points: int | None = None
    is_finished: bool = True


class MatchStats(BaseModel):
    player1_aces: int = 0
    player2_aces: int = 0
    player1_double_faults: int = 0
    player2_double_faults: int = 0
    player1_first_serve_pct: float = 0
    player2_first_serve_pct: float = 0
    player1_break_points_saved: int = 0
    player2_break_points_saved: int = 0
    duration_minutes: int = 0
    player1_break_points_faced: int = 0
    player2_break_points_faced: int = 0


class MatchEventItem(BaseModel):
    id: int
    event_type: str
    set_number: int | None = None
    game_number: int | None = None
    player_id: int | None = None
    payload_json: dict = Field(default_factory=dict)
    created_at: datetime
    importance: str | None = None


class MatchPreview(BaseModel):
    h2h_summary: dict
    player1_form: list[str]
    player2_form: list[str]
    notes: list[str]


class MatchDetail(MatchSummary):
    best_of_sets: int
    winner_id: int | None = None
    score: MatchScore
    sets: list[MatchSetItem] = Field(default_factory=list)
    stats: MatchStats | None = None
    timeline: list[MatchEventItem] = Field(default_factory=list)
    h2h: dict = Field(default_factory=dict)
    related_news: list[NewsArticleSummary] = Field(default_factory=list)


class MatchStatusUpdateRequest(BaseModel):
    status: str


class MatchScoreUpdateRequest(BaseModel):
    score_summary: str
    sets: list[MatchSetItem] = Field(default_factory=list)


class MatchStatsUpdateRequest(BaseModel):
    stats: MatchStats


class MatchEventCreateRequest(BaseModel):
    event_type: str
    set_number: int | None = None
    game_number: int | None = None
    player_id: int | None = None
    payload_json: dict = Field(default_factory=dict)
