from pydantic import BaseModel, Field

from source.schemas.pydantic.match import MatchSummary
from source.schemas.pydantic.news import NewsArticleSummary
from source.schemas.pydantic.player import PlayerSummary
from source.schemas.pydantic.tournament import TournamentSummary


class SearchResults(BaseModel):
    players: list[PlayerSummary] = Field(default_factory=list)
    tournaments: list[TournamentSummary] = Field(default_factory=list)
    matches: list[MatchSummary] = Field(default_factory=list)
    news: list[NewsArticleSummary] = Field(default_factory=list)


class SearchSuggestion(BaseModel):
    text: str
    entity_type: str
