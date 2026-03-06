from __future__ import annotations

from datetime import date
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, status

from source.config.settings import settings
from source.db.models import Match, MatchEvent, Player, RankingSnapshot
from source.db.session import db_session_manager
from source.repositories import DiscoveryRepository, NewsRepository
from source.schemas.pydantic.common import PaginatedResponse, PaginationMeta, SuccessResponse
from source.schemas.pydantic.match import MatchDetail, MatchEventItem, MatchSummary
from source.schemas.pydantic.ranking import RankingEntry, RankingSnapshotItem
from source.schemas.pydantic.search import SearchResults, SearchSuggestion
from source.services.cache_service import CacheService
from source.services.portal_query_service import PortalQueryService


class PublicDataService:
    def __init__(self) -> None:
        self.repo = DiscoveryRepository()
        self.news = NewsRepository()
        self.query = PortalQueryService()
        self.cache = CacheService()

    async def _cached(self, key: str, schema: Any, loader: Callable[[], Awaitable[Any]], ttl_seconds: int | None = None) -> Any:
        return await self.cache.get_or_set(key=key, schema=schema, loader=loader, ttl_seconds=ttl_seconds)

    @staticmethod
    def _meta(page: int, per_page: int, total: int) -> PaginationMeta:
        total_pages = max((total + per_page - 1) // per_page, 1) if per_page else 1
        return PaginationMeta(page=page, per_page=per_page, total=total, total_pages=total_pages)

    @staticmethod
    def _ranking_entry(snapshot: RankingSnapshot, players: dict[int, Player]) -> RankingEntry:
        player = players.get(snapshot.player_id)
        if player is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Ranking player not found')
        return RankingEntry(position=snapshot.rank_position, player_id=player.id, player_name=player.full_name, country_code=player.country_code, points=snapshot.points, movement=snapshot.movement, ranking_type=snapshot.ranking_type, ranking_date=snapshot.ranking_date)

    async def get_rankings(self, page: int = 1, per_page: int = 100, ranking_type: str | None = None, ranking_date: str | None = None) -> PaginatedResponse[RankingEntry]:
        async def loader() -> PaginatedResponse[RankingEntry]:
            async with db_session_manager.session() as session:
                snapshots = await self.repo.list_rankings(session, ranking_type=ranking_type, ranking_date=ranking_date)
                page_items = snapshots[(page - 1) * per_page:(page - 1) * per_page + per_page]
                players = {item.id: item for item in await self.repo.list_players_by_ids(session, [item.player_id for item in page_items])}
                data = [self._ranking_entry(item, players) for item in page_items]
                return PaginatedResponse(data=data, meta=self._meta(page, per_page, len(snapshots)))

        key = f'rankings:list:{ranking_type or ""}:{ranking_date or ""}:{page}:{per_page}'
        return await self._cached(key, PaginatedResponse[RankingEntry], loader, ttl_seconds=settings.cache.rankings_ttl_seconds)

    async def get_current_rankings(self, ranking_type: str = 'atp') -> SuccessResponse[list[RankingEntry]]:
        async def loader() -> SuccessResponse[list[RankingEntry]]:
            async with db_session_manager.session() as session:
                dates = await self.repo.list_ranking_dates(session, ranking_type=ranking_type)
                if not dates:
                    return SuccessResponse(data=[])
                snapshots = await self.repo.list_rankings(session, ranking_type=ranking_type, ranking_date=dates[0])
                players = {item.id: item for item in await self.repo.list_players_by_ids(session, [item.player_id for item in snapshots])}
                return SuccessResponse(data=[self._ranking_entry(item, players) for item in snapshots])

        return await self._cached(f'rankings:current:{ranking_type}', SuccessResponse[list[RankingEntry]], loader, ttl_seconds=settings.cache.rankings_ttl_seconds)

    async def get_rankings_history(self, ranking_type: str) -> SuccessResponse[list[RankingSnapshotItem]]:
        async def loader() -> SuccessResponse[list[RankingSnapshotItem]]:
            async with db_session_manager.session() as session:
                dates = await self.repo.list_ranking_dates(session, ranking_type=ranking_type)
                players = {item.id: item for item in await self.repo.list_players_by_ids(session, [item.player_id for item in await self.repo.list_rankings(session, ranking_type=ranking_type)])}
                history = []
                for ranking_date in dates:
                    snapshots = await self.repo.list_rankings(session, ranking_type=ranking_type, ranking_date=ranking_date)
                    history.append(RankingSnapshotItem(ranking_type=ranking_type, ranking_date=ranking_date, entries=[self._ranking_entry(item, players) for item in snapshots]))
                return SuccessResponse(data=history)

        return await self._cached(f'rankings:history:{ranking_type}', SuccessResponse[list[RankingSnapshotItem]], loader, ttl_seconds=settings.cache.rankings_ttl_seconds)

    async def get_player_rankings(self, player_id: int) -> SuccessResponse[list[dict]]:
        return await self.query.get_player_ranking_history(player_id)

    async def get_race_rankings(self) -> SuccessResponse[list[RankingEntry]]:
        return await self._cached('rankings:race', SuccessResponse[list[RankingEntry]], lambda: self.get_current_rankings('atp'), ttl_seconds=settings.cache.rankings_ttl_seconds)

    @staticmethod
    def _match_score_value(match: Match, players: dict[int, Player]) -> str:
        return ' '.join(filter(None, [players.get(match.player1_id).full_name if players.get(match.player1_id) else None, 'vs', players.get(match.player2_id).full_name if players.get(match.player2_id) else None]))

    async def search(self, q: str) -> SuccessResponse[SearchResults]:
        async def loader() -> SuccessResponse[SearchResults]:
            async with db_session_manager.session() as session:
                players = await self.repo.search_players(session, q)
                tournaments = await self.repo.search_tournaments(session, q)
                news = await self.repo.search_news(session, q)
                matches = await self.repo.search_matches(session, q)
                match_payload = []
                for match in matches:
                    try:
                        match_payload.append((await self.query.get_match(match.id)).data)
                    except HTTPException:
                        continue
                tournament_payload = [self.query._tournament_summary(item) for item in tournaments]
                player_matches = {item.id: [] for item in players}
                player_payload = [self.query._player_summary(item, player_matches[item.id]) for item in players]
                categories = {category.id: category for category in await self.news.list_categories(session)}
                news_payload = [self.query._news_summary(item, categories.get(item.category_id)) for item in news]
                return SuccessResponse(data=SearchResults(players=player_payload, tournaments=tournament_payload, matches=[MatchSummary.model_validate(item.model_dump()) for item in match_payload], news=news_payload))

        return await self._cached(f'search:query:{q.strip().lower()}', SuccessResponse[SearchResults], loader)

    async def search_suggestions(self, q: str) -> SuccessResponse[list[SearchSuggestion]]:
        async def loader() -> SuccessResponse[list[SearchSuggestion]]:
            results = (await self.search(q)).data
            suggestions: list[SearchSuggestion] = []
            for item in results.players[:3]:
                suggestions.append(SearchSuggestion(text=item.full_name, entity_type='player'))
            for item in results.tournaments[:3]:
                suggestions.append(SearchSuggestion(text=item.name, entity_type='tournament'))
            for item in results.news[:3]:
                suggestions.append(SearchSuggestion(text=item.title, entity_type='news'))
            for item in results.matches[:3]:
                suggestions.append(SearchSuggestion(text=f'{item.player1_name} vs {item.player2_name}', entity_type='match'))
            deduped: list[SearchSuggestion] = []
            seen = set()
            for item in suggestions:
                key = (item.entity_type, item.text.lower())
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
            return SuccessResponse(data=deduped[:8])

        return await self._cached(f'search:suggestions:{q.strip().lower()}', SuccessResponse[list[SearchSuggestion]], loader)

    async def list_live_matches(self) -> SuccessResponse[list[MatchSummary]]:
        async def loader() -> SuccessResponse[list[MatchSummary]]:
            async with db_session_manager.session() as session:
                matches = await self.repo.list_live_matches(session, today=date.today())
                data = []
                for match in matches:
                    try:
                        data.append((await self.query.get_match(match.id)).data)
                    except HTTPException:
                        continue
                return SuccessResponse(data=[MatchSummary.model_validate(item.model_dump()) for item in data])

        return await self._cached('live:list', SuccessResponse[list[MatchSummary]], loader, ttl_seconds=settings.cache.live_ttl_seconds)

    async def get_live_match(self, match_id: int) -> SuccessResponse[MatchDetail]:
        return await self._cached(f'live:match:{match_id}', SuccessResponse[MatchDetail], lambda: self.query.get_match(match_id), ttl_seconds=settings.cache.live_ttl_seconds)

    async def get_live_feed(self) -> SuccessResponse[list[MatchEventItem]]:
        async def loader() -> SuccessResponse[list[MatchEventItem]]:
            async with db_session_manager.session() as session:
                events = await self.repo.list_live_events(session)
                return SuccessResponse(data=[MatchEventItem(id=item.id, event_type=item.event_type, set_number=item.set_number, game_number=item.game_number, player_id=item.player_id, payload_json=item.payload_json or {}, created_at=item.created_at) for item in events])

        return await self._cached('live:feed', SuccessResponse[list[MatchEventItem]], loader, ttl_seconds=settings.cache.live_ttl_seconds)
