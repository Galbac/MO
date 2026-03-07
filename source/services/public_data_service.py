from __future__ import annotations

from datetime import UTC, date, datetime
import difflib
import json
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, status

from source.config.settings import settings
from source.db.models import Match, MatchEvent, Player, RankingSnapshot
from source.db.session import db_session_manager
from source.repositories import DiscoveryRepository, NewsRepository
from source.schemas.pydantic.common import PaginatedResponse, PaginationMeta, SuccessResponse
from source.schemas.pydantic.match import MatchDetail, MatchEventItem, MatchSummary
from source.schemas.pydantic.ranking import PlayerRankingRecord, RankingEntry, RankingSnapshotItem
from source.schemas.pydantic.search import SearchResults, SearchSuggestion
from source.services.cache_service import CacheService
from source.services.portal_query_service import PortalQueryService


class PublicDataService:
    ALLOWED_SEARCH_TYPES = {"players", "tournaments", "matches", "news"}

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

    @staticmethod
    def _sort_matches_for_search(matches: list[MatchSummary]) -> list[MatchSummary]:
        def rank(item: MatchSummary) -> tuple[int, datetime, int]:
            status_rank = 0 if item.status == 'live' else 1 if item.status in {'about_to_start', 'scheduled'} else 2
            return (status_rank, item.scheduled_at, item.id)

        return sorted(matches, key=rank)

    async def get_rankings(self, page: int = 1, per_page: int = 100, ranking_type: str | None = None, ranking_date: str | None = None) -> PaginatedResponse[RankingEntry]:
        async def loader() -> PaginatedResponse[RankingEntry]:
            async with db_session_manager.session() as session:
                resolved_ranking_date = ranking_date
                if resolved_ranking_date is None:
                    available_dates = await self.repo.list_ranking_dates(session, ranking_type=ranking_type)
                    resolved_ranking_date = available_dates[0] if available_dates else None
                snapshots = await self.repo.list_rankings(session, ranking_type=ranking_type, ranking_date=resolved_ranking_date)
                page_items = snapshots[(page - 1) * per_page:(page - 1) * per_page + per_page]
                players = {item.id: item for item in await self.repo.list_players_by_ids(session, [item.player_id for item in page_items])}
                data = [self._ranking_entry(item, players) for item in page_items]
                response = PaginatedResponse(data=data, meta=self._meta(page, per_page, len(snapshots)))
                response.meta = response.meta.model_copy(update={'total': len(snapshots)})
                return response

        key = f'rankings:list:{ranking_type or ""}:{ranking_date or "latest"}:{page}:{per_page}'
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
                if not dates:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Ranking history not found')
                all_snapshots = await self.repo.list_rankings(session, ranking_type=ranking_type)
                grouped: dict[str, list[RankingSnapshot]] = {}
                for item in all_snapshots:
                    grouped.setdefault(item.ranking_date, []).append(item)
                player_ids = sorted({item.player_id for item in all_snapshots})
                players = {item.id: item for item in await self.repo.list_players_by_ids(session, player_ids)}
                history = []
                for ranking_date in dates:
                    snapshots = grouped.get(ranking_date, [])
                    entries = [self._ranking_entry(item, players) for item in snapshots]
                    history.append(RankingSnapshotItem(ranking_type=ranking_type, ranking_date=ranking_date, entries=entries, total_entries=len(entries)))
                return SuccessResponse(data=history)

        return await self._cached(f'rankings:history:{ranking_type}', SuccessResponse[list[RankingSnapshotItem]], loader, ttl_seconds=settings.cache.rankings_ttl_seconds)

    async def get_player_rankings(self, player_id: int) -> SuccessResponse[list[PlayerRankingRecord]]:
        async def loader() -> SuccessResponse[list[PlayerRankingRecord]]:
            query_history = await self.query.get_player_ranking_history(player_id)
            if query_history.data:
                normalized = []
                for item in query_history.data:
                    if isinstance(item, dict) and {'ranking_type', 'ranking_date', 'rank_position', 'points', 'movement'} <= set(item):
                        normalized.append(
                            PlayerRankingRecord(
                                ranking_type=str(item['ranking_type']),
                                ranking_date=str(item['ranking_date']),
                                position=int(item['rank_position']),
                                points=int(item['points']),
                                movement=int(item['movement']),
                            )
                        )
                    elif all(hasattr(item, attr) for attr in ('ranking_type', 'ranking_date', 'rank_position', 'points', 'movement')):
                        normalized.append(
                            PlayerRankingRecord(
                                ranking_type=str(item.ranking_type),
                                ranking_date=str(item.ranking_date),
                                position=int(item.rank_position),
                                points=int(item.points),
                                movement=int(item.movement),
                            )
                        )
                    else:
                        return SuccessResponse(data=query_history.data)
                if normalized:
                    return SuccessResponse(data=normalized)
            async with db_session_manager.session() as session:
                player = await self.repo.list_players_by_ids(session, [player_id])
                if not player:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Player not found')
                snapshots = await self.repo.list_rankings_for_player(session, player_id=player_id)
                payload = [
                    PlayerRankingRecord(
                        ranking_type=item.ranking_type,
                        ranking_date=item.ranking_date,
                        position=item.rank_position,
                        points=item.points,
                        movement=item.movement,
                    )
                    for item in snapshots
                ]
                return SuccessResponse(data=payload)

        return await self._cached(
            f'rankings:player:{player_id}',
            SuccessResponse[list[PlayerRankingRecord]],
            loader,
            ttl_seconds=settings.cache.rankings_ttl_seconds,
        )

    async def get_race_rankings(self) -> SuccessResponse[list[RankingEntry]]:
        async def loader() -> SuccessResponse[list[RankingEntry]]:
            season_year = datetime.now(tz=UTC).year
            async with db_session_manager.session() as session:
                rows = await self.repo.list_finished_matches_for_season(session, season_year=season_year)
                if not rows:
                    current = await self.get_current_rankings('atp')
                    return SuccessResponse(
                        data=[
                            item.model_copy(update={'ranking_type': 'race', 'movement': 0})
                            for item in current.data
                        ]
                    )

                player_ids = sorted({match.player1_id for match, _ in rows} | {match.player2_id for match, _ in rows})
                players = {item.id: item for item in await self.repo.list_players_by_ids(session, player_ids)}

                def round_multiplier(round_code: str | None) -> float:
                    mapping = {
                        'F': 1.0,
                        'SF': 0.6,
                        'QF': 0.36,
                        'R16': 0.18,
                        'R32': 0.09,
                        'R64': 0.045,
                    }
                    return mapping.get((round_code or '').upper(), 0.03)

                points_by_player: dict[int, int] = {}
                latest_match_at: dict[int, datetime] = {}

                for match, tournament in rows:
                    base_points = int(tournament.points_winner or 0)
                    if base_points <= 0:
                        continue
                    winner_points = base_points
                    loser_points = max(int(base_points * round_multiplier(match.round_code)), 0)
                    awarded = (
                        (match.winner_id, winner_points),
                        (
                            match.player2_id if match.winner_id == match.player1_id else match.player1_id,
                            loser_points,
                        ),
                    )
                    for player_id, value in awarded:
                        if player_id is None:
                            continue
                        points_by_player[player_id] = points_by_player.get(player_id, 0) + value
                        scheduled_at = match.scheduled_at
                        if scheduled_at is not None:
                            current_latest = latest_match_at.get(player_id)
                            if current_latest is None or scheduled_at > current_latest:
                                latest_match_at[player_id] = scheduled_at

                ordered = sorted(
                    points_by_player.items(),
                    key=lambda item: (-item[1], latest_match_at.get(item[0], datetime.min.replace(tzinfo=UTC)), item[0]),
                )
                payload: list[RankingEntry] = []
                previous_points: int | None = None
                previous_position = 0
                for index, (player_id, points) in enumerate(ordered, start=1):
                    player = players.get(player_id)
                    if player is None:
                        continue
                    position = previous_position if previous_points == points else index
                    movement = 0 if player.current_rank is None else int(player.current_rank) - int(position)
                    payload.append(
                        RankingEntry(
                            position=position,
                            player_id=player.id,
                            player_name=player.full_name,
                            country_code=player.country_code,
                            points=points,
                            movement=movement,
                            ranking_type='race',
                            ranking_date=date.today().isoformat(),
                        )
                    )
                    previous_points = points
                    previous_position = position
                return SuccessResponse(data=payload)

        return await self._cached(
            'rankings:race',
            SuccessResponse[list[RankingEntry]],
            loader,
            ttl_seconds=settings.cache.rankings_ttl_seconds,
        )

    def _search_index_path(self) -> Path:
        return Path(settings.maintenance.artifacts_dir) / 'search_index.json'

    def _load_search_index(self) -> dict[str, Any]:
        path = self._search_index_path()
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _normalize_search_text(value: str) -> str:
        return ''.join(str(value or '').lower().split())

    def _fuzzy_index_matches(self, query: str, allowed_types: set[str]) -> dict[str, list[str]]:
        index_payload = self._load_search_index()
        normalized_query = self._normalize_search_text(query)
        results: dict[str, list[str]] = {key: [] for key in self.ALLOWED_SEARCH_TYPES}
        if not normalized_query:
            return results
        for entity_type in allowed_types:
            documents = index_payload.get(entity_type, [])
            ranked: list[tuple[float, str]] = []
            for document in documents:
                title = str(document.get('title') or '').strip()
                keywords = [str(item).strip() for item in list(document.get('keywords') or []) if str(item).strip()]
                variants = [title, *keywords]
                best = 0.0
                for variant in variants:
                    normalized_variant = self._normalize_search_text(variant)
                    if not normalized_variant:
                        continue
                    if normalized_query in normalized_variant or normalized_variant in normalized_query:
                        best = max(best, 1.0)
                    else:
                        best = max(best, difflib.SequenceMatcher(a=normalized_query, b=normalized_variant).ratio())
                if best >= 0.74 and title:
                    ranked.append((best, title))
            ranked.sort(key=lambda item: (-item[0], item[1]))
            deduped: list[str] = []
            seen: set[str] = set()
            for _, title in ranked:
                key = title.lower()
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(title)
                if len(deduped) >= 3:
                    break
            results[entity_type] = deduped
        return results

    @staticmethod
    def _match_score_value(match: Match, players: dict[int, Player]) -> str:
        return ' '.join(filter(None, [players.get(match.player1_id).full_name if players.get(match.player1_id) else None, 'vs', players.get(match.player2_id).full_name if players.get(match.player2_id) else None]))
    @classmethod
    def _normalize_search_query(cls, query: str) -> str:
        normalized = ' '.join(str(query or '').strip().split())
        if not normalized:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Search query is required')
        return normalized[:120]

    @classmethod
    def _normalize_search_types(cls, types: list[str] | None) -> set[str]:
        if not types:
            return set(cls.ALLOWED_SEARCH_TYPES)
        normalized = {str(item).strip().lower() for item in types if str(item).strip()}
        if not normalized:
            return set(cls.ALLOWED_SEARCH_TYPES)
        invalid = sorted(normalized - cls.ALLOWED_SEARCH_TYPES)
        if invalid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'Unsupported search types: {", ".join(invalid)}')
        return normalized


    async def search(self, q: str, types: list[str] | None = None) -> SuccessResponse[SearchResults]:
        async def loader() -> SuccessResponse[SearchResults]:
            normalized_query = self._normalize_search_query(q)
            allowed_types = self._normalize_search_types(types)
            async with db_session_manager.session() as session:
                players = await self.repo.search_players(session, normalized_query) if 'players' in allowed_types else []
                tournaments = await self.repo.search_tournaments(session, normalized_query) if 'tournaments' in allowed_types else []
                news = await self.repo.search_news(session, normalized_query) if 'news' in allowed_types else []
                matches = await self.repo.search_matches(session, normalized_query) if 'matches' in allowed_types else []

                if not any([players, tournaments, news, matches]):
                    fuzzy_matches = self._fuzzy_index_matches(normalized_query, allowed_types)
                    if 'players' in allowed_types and not players:
                        for title in fuzzy_matches['players']:
                            players.extend(await self.repo.search_players(session, title, limit=3))
                    if 'tournaments' in allowed_types and not tournaments:
                        for title in fuzzy_matches['tournaments']:
                            tournaments.extend(await self.repo.search_tournaments(session, title, limit=3))
                    if 'news' in allowed_types and not news:
                        for title in fuzzy_matches['news']:
                            news.extend(await self.repo.search_news(session, title, limit=3))
                    if 'matches' in allowed_types and not matches:
                        for title in fuzzy_matches['matches']:
                            matches.extend(await self.repo.search_matches(session, title, limit=3))

                query_terms = [item for item in normalized_query.lower().replace('-', ' ').split() if item]
                direct_match_payload: list[MatchSummary] = []
                if len(query_terms) >= 2:
                    supplemental_player_ids = {item.id for item in players}
                    for term in query_terms:
                        for player in await self.repo.search_players(session, term, limit=10):
                            supplemental_player_ids.add(player.id)
                    if supplemental_player_ids:
                        upcoming = await self.query.get_upcoming_matches()
                        results = await self.query.get_match_results()
                        combined_matches = [*upcoming.data, *results.data]
                        for item in combined_matches:
                            haystack = f'{item.player1_name} {item.player2_name} {item.slug}'.lower()
                            ids = {item.player1_id, item.player2_id}
                            if ids.issubset(supplemental_player_ids) or all(term in haystack for term in query_terms):
                                direct_match_payload.append(item)

                dedup_matches: dict[int, Match] = {item.id: item for item in matches}
                match_payload: dict[int, MatchSummary] = {item.id: item for item in direct_match_payload}
                for match in dedup_matches.values():
                    try:
                        match_payload[match.id] = MatchSummary.model_validate((await self.query.get_match(match.id)).data.model_dump())
                    except HTTPException:
                        continue
                tournament_payload = [self.query._tournament_summary(item) for item in tournaments]
                player_matches = {}
                for item in players:
                    try:
                        player_matches[item.id] = await self.query.players.get_matches(session, item.id)
                    except Exception:  # noqa: BLE001
                        player_matches[item.id] = []
                player_aggregates = {item.id: self.query._load_player_aggregate(item.id) for item in players}
                player_payload = []
                for item in players:
                    try:
                        player_payload.append(self.query._player_summary(item, player_matches[item.id], player_aggregates[item.id]))
                    except TypeError:
                        player_payload.append(self.query._player_summary(item, player_matches[item.id]))
                categories = {category.id: category for category in await self.news.list_categories(session)}
                news_payload = [self.query._news_summary(item, categories.get(item.category_id), await self.query._news_tags(session, item.id)) for item in news]
                sorted_matches = self._sort_matches_for_search(list(match_payload.values()))
                return SuccessResponse(data=SearchResults(players=player_payload, tournaments=tournament_payload, matches=sorted_matches, news=news_payload))

        normalized_query = self._normalize_search_query(q)
        normalized_types = sorted(self._normalize_search_types(types))
        cache_key = f"search:query:{normalized_query.lower()}:{'|'.join(normalized_types)}"
        return await self._cached(cache_key, SuccessResponse[SearchResults], loader)

    async def search_suggestions(self, q: str, types: list[str] | None = None) -> SuccessResponse[list[SearchSuggestion]]:
        async def loader() -> SuccessResponse[list[SearchSuggestion]]:
            results = (await self.search(q, types=types)).data
            suggestions: list[SearchSuggestion] = []
            for item in results.players[:3]:
                suggestions.append(SearchSuggestion(text=item.full_name, entity_type='player', entity_id=item.id, slug=item.slug, url=f'/players/{item.slug}'))
            for item in results.tournaments[:3]:
                suggestions.append(SearchSuggestion(text=item.name, entity_type='tournament', entity_id=item.id, slug=item.slug, url=f'/tournaments/{item.slug}'))
            for item in results.news[:3]:
                suggestions.append(SearchSuggestion(text=item.title, entity_type='news', entity_id=item.id, slug=item.slug, url=f'/news/{item.slug}'))
            for item in results.matches[:3]:
                suggestions.append(SearchSuggestion(text=f'{item.player1_name} vs {item.player2_name}', entity_type='match', entity_id=item.id, slug=item.slug, url=f'/matches/{item.slug}'))
            deduped: list[SearchSuggestion] = []
            seen = set()
            for item in suggestions:
                key = (item.entity_type, item.text.lower())
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
            if deduped:
                return SuccessResponse(data=deduped[:8])
            fuzzy_matches = self._fuzzy_index_matches(self._normalize_search_query(q), self._normalize_search_types(types))
            fallback: list[SearchSuggestion] = []
            for title in fuzzy_matches['players']:
                fallback.append(SearchSuggestion(text=title, entity_type='player'))
            for title in fuzzy_matches['tournaments']:
                fallback.append(SearchSuggestion(text=title, entity_type='tournament'))
            for title in fuzzy_matches['news']:
                fallback.append(SearchSuggestion(text=title, entity_type='news'))
            for title in fuzzy_matches['matches']:
                fallback.append(SearchSuggestion(text=title, entity_type='match'))
            return SuccessResponse(data=fallback[:8])

        normalized_query = self._normalize_search_query(q)
        normalized_types = sorted(self._normalize_search_types(types))
        cache_key = f"search:suggestions:{normalized_query.lower()}:{'|'.join(normalized_types)}"
        return await self._cached(cache_key, SuccessResponse[list[SearchSuggestion]], loader)

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
        async def loader() -> SuccessResponse[MatchDetail]:
            detail = (await self.query.get_match(match_id)).data
            if detail.status not in {'live', 'about_to_start'}:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Live match not found')
            return SuccessResponse(data=detail, meta={'live_status': detail.status, 'timeline_events': len(detail.timeline)})

        return await self._cached(f'live:match:{match_id}', SuccessResponse[MatchDetail], loader, ttl_seconds=settings.cache.live_ttl_seconds)

    async def get_live_feed(self) -> SuccessResponse[list[MatchEventItem]]:
        async def loader() -> SuccessResponse[list[MatchEventItem]]:
            async with db_session_manager.session() as session:
                live_matches = await self.repo.list_live_matches(session, today=date.today())
                live_match_ids = {item.id for item in live_matches}
                events = await self.repo.list_live_events(session)
                filtered = [
                    MatchEventItem(id=item.id, event_type=item.event_type, set_number=item.set_number, game_number=item.game_number, player_id=item.player_id, payload_json=item.payload_json or {}, created_at=item.created_at)
                    for item in events
                    if getattr(item, 'match_id', None) in live_match_ids or not hasattr(item, 'match_id')
                ]
                return SuccessResponse(data=filtered, meta={'live_matches': len(live_match_ids), 'events_returned': len(filtered)})

        return await self._cached('live:feed', SuccessResponse[list[MatchEventItem]], loader, ttl_seconds=settings.cache.live_ttl_seconds)
