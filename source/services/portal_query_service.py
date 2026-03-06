from __future__ import annotations

from datetime import date, datetime
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, status

from source.config.settings import settings
from source.db.models import HeadToHead, Match, MatchEvent, MatchSet, MatchStats, NewsArticle, NewsCategory, Player, RankingSnapshot, Tournament
from source.db.session import db_session_manager
from source.repositories import MatchRepository, NewsRepository, PlayerRepository, TournamentRepository
from source.schemas.pydantic.common import PaginatedResponse, PaginationMeta, SuccessResponse
from source.schemas.pydantic.match import MatchDetail, MatchEventItem, MatchPreview, MatchScore, MatchSetItem, MatchStats as MatchStatsSchema, MatchSummary
from source.schemas.pydantic.news import NewsArticleDetail, NewsArticleSummary, NewsCategoryItem, TagItem
from source.schemas.pydantic.player import H2HResponse, PlayerComparison, PlayerDetail, PlayerNewsItem, PlayerStats, PlayerSummary, RankingHistoryPoint, SeoMeta, TitleItem, UpcomingMatchItem
from source.schemas.pydantic.tournament import ChampionItem, DrawMatchItem, TournamentDetail, TournamentSummary
from source.services.cache_service import CacheService


class PortalQueryService:
    def __init__(self) -> None:
        self.players = PlayerRepository()
        self.tournaments = TournamentRepository()
        self.matches = MatchRepository()
        self.news = NewsRepository()
        self.cache = CacheService()

    async def _cached(self, key: str, schema: Any, loader: Callable[[], Awaitable[Any]], ttl_seconds: int | None = None) -> Any:
        return await self.cache.get_or_set(key=key, schema=schema, loader=loader, ttl_seconds=ttl_seconds)

    @staticmethod
    def _paginate_meta(page: int, per_page: int, total: int) -> PaginationMeta:
        total_pages = max((total + per_page - 1) // per_page, 1) if per_page else 1
        return PaginationMeta(page=page, per_page=per_page, total=total, total_pages=total_pages)

    @staticmethod
    def _player_form(matches: list[Match], player_id: int) -> list[str]:
        ordered = sorted(matches, key=lambda item: item.scheduled_at or datetime.min, reverse=True)[:5]
        return ['W' if item.winner_id == player_id else 'L' for item in ordered if item.winner_id is not None]

    def _player_summary(self, player: Player, matches: list[Match] | None = None) -> PlayerSummary:
        return PlayerSummary(
            id=player.id,
            slug=player.slug,
            full_name=player.full_name,
            country_code=player.country_code,
            current_rank=player.current_rank,
            current_points=player.current_points,
            photo_url=player.photo_url,
            form=self._player_form(matches or [], player.id),
        )

    @staticmethod
    def _player_stats(matches: list[Match], player_id: int) -> PlayerStats:
        completed = [item for item in matches if item.winner_id is not None]
        wins = sum(1 for item in completed if item.winner_id == player_id)
        losses = sum(1 for item in completed if item.winner_id and item.winner_id != player_id)
        season = max((item.scheduled_at.year for item in matches if item.scheduled_at), default=date.today().year)
        return PlayerStats(
            season=season,
            matches_played=len(completed),
            wins=wins,
            losses=losses,
            win_rate=round((wins / len(completed)) * 100, 1) if completed else 0.0,
            hard_record=f"{wins}-{losses}",
            clay_record="0-0",
            grass_record="0-0",
        )

    @staticmethod
    def _ranking_points(snapshots: list[RankingSnapshot]) -> list[RankingHistoryPoint]:
        return [RankingHistoryPoint(ranking_date=item.ranking_date, rank_position=item.rank_position, points=item.points, movement=item.movement) for item in snapshots]

    @staticmethod
    def _news_category_item(category: NewsCategory | None) -> NewsCategoryItem | None:
        if category is None:
            return None
        return NewsCategoryItem(id=category.id, slug=category.slug, name=category.name)

    @staticmethod
    def _news_summary(article: NewsArticle, category: NewsCategory | None = None) -> NewsArticleSummary:
        return NewsArticleSummary(
            id=article.id,
            slug=article.slug,
            title=article.title,
            subtitle=article.subtitle,
            lead=article.lead,
            cover_image_url=article.cover_image_url,
            status=article.status,
            published_at=article.published_at.isoformat() if article.published_at else None,
            category=PortalQueryService._news_category_item(category),
            tags=[],
        )

    @staticmethod
    def _tournament_summary(tournament: Tournament) -> TournamentSummary:
        return TournamentSummary(
            id=tournament.id,
            slug=tournament.slug,
            name=tournament.name,
            category=tournament.category,
            surface=tournament.surface,
            season_year=tournament.season_year,
            start_date=tournament.start_date.isoformat() if tournament.start_date else None,
            end_date=tournament.end_date.isoformat() if tournament.end_date else None,
            status=tournament.status,
            city=tournament.city,
        )

    @staticmethod
    def _event_item(item: MatchEvent) -> MatchEventItem:
        return MatchEventItem(id=item.id, event_type=item.event_type, set_number=item.set_number, game_number=item.game_number, player_id=item.player_id, payload_json=item.payload_json or {}, created_at=item.created_at)

    @staticmethod
    def _set_item(item: MatchSet) -> MatchSetItem:
        return MatchSetItem(set_number=item.set_number, player1_games=item.player1_games, player2_games=item.player2_games, tiebreak_player1_points=item.tiebreak_player1_points, tiebreak_player2_points=item.tiebreak_player2_points, is_finished=item.is_finished)

    @staticmethod
    def _stats_item(item: MatchStats | None) -> MatchStatsSchema:
        if item is None:
            return MatchStatsSchema()
        return MatchStatsSchema(player1_aces=item.player1_aces, player2_aces=item.player2_aces, player1_double_faults=item.player1_double_faults, player2_double_faults=item.player2_double_faults, player1_first_serve_pct=float(item.player1_first_serve_pct), player2_first_serve_pct=float(item.player2_first_serve_pct), player1_break_points_saved=item.player1_break_points_saved, player2_break_points_saved=item.player2_break_points_saved, duration_minutes=item.duration_minutes)

    @staticmethod
    def _h2h_item(item: HeadToHead | None) -> dict:
        return H2HResponse.model_validate(item, from_attributes=True).model_dump() if item else {}

    @staticmethod
    def _match_score(sets: list[MatchSet], summary: str | None, serving_player_id: int | None) -> MatchScore:
        return MatchScore(sets=[f"{item.player1_games}-{item.player2_games}" for item in sets], current_game=summary, serving_player_id=serving_player_id)

    @staticmethod
    def _resolve_opponent(match: Match, player_id: int, players: dict[int, Player]) -> Player | None:
        opponent_id = match.player2_id if match.player1_id == player_id else match.player1_id
        return players.get(opponent_id)

    def _match_summary(self, match: Match, tournament: Tournament, players: dict[int, Player]) -> MatchSummary:
        player1 = players.get(match.player1_id)
        player2 = players.get(match.player2_id)
        if player1 is None or player2 is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Match players are missing')
        return MatchSummary(id=match.id, slug=match.slug, status=match.status, scheduled_at=match.scheduled_at, actual_start_at=match.actual_start_at, actual_end_at=match.actual_end_at, player1_id=match.player1_id, player2_id=match.player2_id, player1_name=player1.full_name, player2_name=player2.full_name, tournament_id=tournament.id, tournament_name=tournament.name, round_code=match.round_code, court_name=match.court_name, score_summary=match.score_summary)

    async def _players_map(self, session, player_ids: set[int]) -> dict[int, Player]:
        items = [await self.players.get(session, player_id) for player_id in sorted(player_ids)]
        return {item.id: item for item in items if item is not None}

    async def list_players(self, search, country_code, hand, status, rank_from, rank_to, page, per_page):
        async def loader() -> PaginatedResponse[PlayerSummary]:
            async with db_session_manager.session() as session:
                items, total = await self.players.list(session, search=search, country_code=country_code, hand=hand, status=status, rank_from=rank_from, rank_to=rank_to, page=page, per_page=per_page)
                player_matches = {item.id: await self.players.get_matches(session, item.id) for item in items}
                return PaginatedResponse(data=[self._player_summary(item, player_matches.get(item.id, [])) for item in items], meta=self._paginate_meta(page, per_page, total))

        key = f'players:list:{search or ""}:{country_code or ""}:{hand or ""}:{status or ""}:{rank_from or ""}:{rank_to or ""}:{page}:{per_page}'
        return await self._cached(key, PaginatedResponse[PlayerSummary], loader)

    async def get_player(self, player_id: int):
        async def loader() -> SuccessResponse[PlayerDetail]:
            async with db_session_manager.session() as session:
                player = await self.players.get(session, player_id)
                if player is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Player not found')
                matches = await self.players.get_matches(session, player_id)
                rankings = await self.players.get_ranking_history(session, player_id)
                player_ids = {value for match in matches for value in (match.player1_id, match.player2_id)}
                players = await self._players_map(session, player_ids)
                tournaments = {match.tournament_id: await self.tournaments.get(session, match.tournament_id) for match in matches}
                recent_matches = [self._match_summary(match, tournaments[match.tournament_id], players).model_dump() for match in sorted(matches, key=lambda item: item.scheduled_at or datetime.min, reverse=True)[:5] if tournaments.get(match.tournament_id)]
                upcoming = next((item for item in sorted(matches, key=lambda m: m.scheduled_at or datetime.max) if item.status in {'scheduled', 'about_to_start', 'live'}), None)
                upcoming_match = None
                if upcoming and tournaments.get(upcoming.tournament_id):
                    opponent = self._resolve_opponent(upcoming, player_id, players)
                    upcoming_match = UpcomingMatchItem(match_id=upcoming.id, slug=upcoming.slug, tournament_name=tournaments[upcoming.tournament_id].name, opponent_name=opponent.full_name if opponent else '', scheduled_at=upcoming.scheduled_at.isoformat(), status=upcoming.status)
                titles = []
                for match in matches:
                    if match.winner_id == player_id and match.round_code == 'F' and tournaments.get(match.tournament_id):
                        tournament = tournaments[match.tournament_id]
                        titles.append(TitleItem(tournament_name=tournament.name, season_year=tournament.season_year, surface=tournament.surface, category=tournament.category))
                detail = PlayerDetail(**self._player_summary(player, matches).model_dump(), first_name=player.first_name, last_name=player.last_name, country_name=player.country_name, birth_date=player.birth_date, height_cm=player.height_cm, weight_kg=player.weight_kg, hand=player.hand, backhand=player.backhand, biography=player.biography, status=player.status, stats=self._player_stats(matches, player_id), recent_matches=recent_matches, upcoming_match=upcoming_match, ranking_history=self._ranking_points(rankings), titles=titles, seo=SeoMeta(title=player.full_name, description=player.biography or player.full_name, canonical_url=f'/players/{player.slug}'))
                return SuccessResponse(data=detail)

        return await self._cached(f'players:detail:{player_id}', SuccessResponse[PlayerDetail], loader)

    async def get_player_stats(self, player_id: int):
        return SuccessResponse(data=(await self.get_player(player_id)).data.stats)

    async def get_player_matches(self, player_id: int, page: int, per_page: int):
        async def loader() -> PaginatedResponse[MatchSummary]:
            async with db_session_manager.session() as session:
                matches = await self.players.get_matches(session, player_id)
                player_ids = {value for match in matches for value in (match.player1_id, match.player2_id)}
                players = await self._players_map(session, player_ids)
                tournaments = {match.tournament_id: await self.tournaments.get(session, match.tournament_id) for match in matches}
                items = [self._match_summary(match, tournaments[match.tournament_id], players) for match in matches if tournaments.get(match.tournament_id)]
                total = len(items)
                start = (page - 1) * per_page
                return PaginatedResponse(data=items[start:start + per_page], meta=self._paginate_meta(page, per_page, total))

        return await self._cached(f'players:matches:{player_id}:{page}:{per_page}', PaginatedResponse[MatchSummary], loader)

    async def get_player_ranking_history(self, player_id: int):
        async def loader() -> SuccessResponse[list[RankingHistoryPoint]]:
            async with db_session_manager.session() as session:
                rankings = await self.players.get_ranking_history(session, player_id)
                return SuccessResponse(data=self._ranking_points(rankings))

        return await self._cached(f'players:ranking-history:{player_id}', SuccessResponse[list[RankingHistoryPoint]], loader, ttl_seconds=settings.cache.rankings_ttl_seconds)

    async def get_player_titles(self, player_id: int):
        return SuccessResponse(data=(await self.get_player(player_id)).data.titles)

    async def get_player_news(self, player_id: int):
        async def loader() -> SuccessResponse[list[PlayerNewsItem]]:
            async with db_session_manager.session() as session:
                player = await self.players.get(session, player_id)
                if player is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Player not found')
                items, _ = await self.news.list(session, page=1, per_page=100)
                related = [item for item in items if player.full_name.lower() in ' '.join(filter(None, [item.title, item.subtitle, item.lead, item.content_html])).lower()]
                return SuccessResponse(data=[PlayerNewsItem(id=item.id, slug=item.slug, title=item.title, published_at=item.published_at.isoformat() if item.published_at else None) for item in related])

        return await self._cached(f'players:news:{player_id}', SuccessResponse[list[PlayerNewsItem]], loader)

    async def get_player_upcoming_matches(self, player_id: int):
        return SuccessResponse(data=[(await self.get_player(player_id)).data.upcoming_match] if (await self.get_player(player_id)).data.upcoming_match else [])

    async def get_h2h(self, player1_id: int, player2_id: int):
        left, right = sorted((player1_id, player2_id))

        async def loader() -> SuccessResponse[H2HResponse]:
            async with db_session_manager.session() as session:
                h2h = await self.players.get_h2h(session, player1_id, player2_id)
                if h2h is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='H2H not found')
                return SuccessResponse(data=H2HResponse.model_validate(h2h, from_attributes=True))

        return await self._cached(f'players:h2h:{left}:{right}', SuccessResponse[H2HResponse], loader)

    async def compare_players(self, player1_id: int, player2_id: int):
        left, right = sorted((player1_id, player2_id))

        async def loader() -> SuccessResponse[PlayerComparison]:
            player1 = (await self.get_player(player1_id)).data
            player2 = (await self.get_player(player2_id)).data
            h2h = (await self.get_h2h(player1_id, player2_id)).data.model_dump()
            comparison = {'rank_delta': (player1.current_rank or 0) - (player2.current_rank or 0), 'points_delta': (player1.current_points or 0) - (player2.current_points or 0)}
            return SuccessResponse(data=PlayerComparison(player1=player1, player2=player2, h2h=h2h, comparison=comparison))

        return await self._cached(f'players:compare:{left}:{right}', SuccessResponse[PlayerComparison], loader)

    async def list_tournaments(self, page, per_page):
        async def loader() -> PaginatedResponse[TournamentSummary]:
            async with db_session_manager.session() as session:
                items, total = await self.tournaments.list(session, page=page, per_page=per_page)
                return PaginatedResponse(data=[self._tournament_summary(item) for item in items], meta=self._paginate_meta(page, per_page, total))

        return await self._cached(f'tournaments:list:{page}:{per_page}', PaginatedResponse[TournamentSummary], loader)

    async def get_tournament(self, tournament_id: int):
        async def loader() -> SuccessResponse[TournamentDetail]:
            async with db_session_manager.session() as session:
                tournament = await self.tournaments.get(session, tournament_id)
                if tournament is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tournament not found')
                matches = await self.tournaments.get_matches(session, tournament_id)
                player_ids = {value for match in matches for value in (match.player1_id, match.player2_id)}
                players = await self._players_map(session, player_ids)
                participants = [self._player_summary(item, []).model_dump() for item in players.values()]
                current_matches = [self._match_summary(match, tournament, players).model_dump() for match in matches]
                champions = []
                final_match = next((item for item in matches if item.round_code == 'F' and item.winner_id and players.get(item.winner_id)), None)
                if final_match:
                    winner = players.get(final_match.winner_id)
                    if winner is not None:
                        champions.append(ChampionItem(player_id=winner.id, player_name=winner.full_name, season_year=tournament.season_year))
                data = TournamentDetail(**self._tournament_summary(tournament).model_dump(), short_name=tournament.short_name, indoor=tournament.indoor, country_code=tournament.country_code, prize_money=tournament.prize_money, points_winner=tournament.points_winner, logo_url=tournament.logo_url, description=tournament.description, matches=current_matches, draw=[DrawMatchItem(match_id=match.id, round_code=match.round_code, player1_name=players.get(match.player1_id).full_name if players.get(match.player1_id) else '', player2_name=players.get(match.player2_id).full_name if players.get(match.player2_id) else '', score_summary=match.score_summary) for match in matches], players=participants, champions=champions)
                return SuccessResponse(data=data)

        return await self._cached(f'tournaments:detail:{tournament_id}', SuccessResponse[TournamentDetail], loader)

    async def get_tournament_matches(self, tournament_id: int):
        return SuccessResponse(data=(await self.get_tournament(tournament_id)).data.matches)

    async def get_tournament_draw(self, tournament_id: int):
        return SuccessResponse(data=(await self.get_tournament(tournament_id)).data.draw)

    async def get_tournament_players(self, tournament_id: int):
        return SuccessResponse(data=(await self.get_tournament(tournament_id)).data.players)

    async def get_tournament_champions(self, tournament_id: int):
        return SuccessResponse(data=(await self.get_tournament(tournament_id)).data.champions)

    async def get_tournament_news(self, tournament_id: int):
        async def loader() -> SuccessResponse[list[NewsArticleSummary]]:
            async with db_session_manager.session() as session:
                tournament = await self.tournaments.get(session, tournament_id)
                if tournament is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tournament not found')
                items, _ = await self.news.list(session, page=1, per_page=100)
                categories = {item.id: item for item in await self.news.list_categories(session)}
                related = [item for item in items if tournament.name.lower() in ' '.join(filter(None, [item.title, item.subtitle, item.lead, item.content_html])).lower()]
                return SuccessResponse(data=[self._news_summary(item, categories.get(item.category_id)) for item in related])

        return await self._cached(f'tournaments:news:{tournament_id}', SuccessResponse[list[NewsArticleSummary]], loader)

    async def get_tournament_calendar(self):
        async def loader() -> SuccessResponse[list[TournamentSummary]]:
            payload = await self.list_tournaments(1, 100)
            return SuccessResponse(data=payload.data)

        return await self._cached('tournaments:calendar', SuccessResponse[list[TournamentSummary]], loader)

    async def list_matches(self, page: int, per_page: int, status: str | None):
        async def loader() -> PaginatedResponse[MatchSummary]:
            async with db_session_manager.session() as session:
                items, total = await self.matches.list(session, page=page, per_page=per_page, status=status)
                tournaments = {match.tournament_id: await self.tournaments.get(session, match.tournament_id) for match in items}
                player_ids = {value for match in items for value in (match.player1_id, match.player2_id)}
                players = await self._players_map(session, player_ids)
                data = [self._match_summary(match, tournaments[match.tournament_id], players) for match in items if tournaments.get(match.tournament_id)]
                return PaginatedResponse(data=data, meta=self._paginate_meta(page, per_page, total))

        return await self._cached(f'matches:list:{status or ""}:{page}:{per_page}', PaginatedResponse[MatchSummary], loader)

    async def get_match(self, match_id: int):
        async def loader() -> SuccessResponse[MatchDetail]:
            async with db_session_manager.session() as session:
                match = await self.matches.get(session, match_id)
                if match is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
                tournament = await self.tournaments.get(session, match.tournament_id)
                if tournament is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tournament not found')
                players = await self._players_map(session, {match.player1_id, match.player2_id})
                sets = await self.matches.get_sets(session, match_id)
                stats = await self.matches.get_stats(session, match_id)
                events = await self.matches.get_events(session, match_id)
                h2h = await self.matches.get_h2h(session, match.player1_id, match.player2_id)
                related_news = await self.get_tournament_news(match.tournament_id)
                data = MatchDetail(**self._match_summary(match, tournament, players).model_dump(), best_of_sets=match.best_of_sets, winner_id=match.winner_id, score=self._match_score(sets, match.score_summary, match.player1_id), sets=[self._set_item(item) for item in sets], stats=self._stats_item(stats), timeline=[self._event_item(item) for item in events], h2h=self._h2h_item(h2h), related_news=related_news.data[:2])
                return SuccessResponse(data=data)

        return await self._cached(f'matches:detail:{match_id}', SuccessResponse[MatchDetail], loader)

    async def get_match_score(self, match_id: int):
        return SuccessResponse(data=(await self.get_match(match_id)).data.score)

    async def get_match_stats(self, match_id: int):
        return SuccessResponse(data=(await self.get_match(match_id)).data.stats or MatchStatsSchema())

    async def get_match_timeline(self, match_id: int):
        return SuccessResponse(data=(await self.get_match(match_id)).data.timeline)

    async def get_match_h2h(self, match_id: int):
        return SuccessResponse(data=H2HResponse.model_validate((await self.get_match(match_id)).data.h2h))

    async def get_match_preview(self, match_id: int):
        async def loader() -> SuccessResponse[MatchPreview]:
            detail = (await self.get_match(match_id)).data
            async with db_session_manager.session() as session:
                player1_matches = await self.players.get_matches(session, detail.player1_id or 0) if detail.player1_id else []
                player2_matches = await self.players.get_matches(session, detail.player2_id or 0) if detail.player2_id else []
            return SuccessResponse(data=MatchPreview(h2h_summary=detail.h2h, player1_form=self._player_form(player1_matches, detail.player1_id or 0), player2_form=self._player_form(player2_matches, detail.player2_id or 0), notes=[detail.status, str(detail.best_of_sets)]))

        return await self._cached(f'matches:preview:{match_id}', SuccessResponse[MatchPreview], loader)

    async def get_match_point_by_point(self, match_id: int):
        return await self.get_match_timeline(match_id)

    async def get_upcoming_matches(self):
        async def loader() -> SuccessResponse[list[MatchSummary]]:
            async with db_session_manager.session() as session:
                items = await self.matches.get_upcoming(session)
                tournaments = {match.tournament_id: await self.tournaments.get(session, match.tournament_id) for match in items}
                players = await self._players_map(session, {value for match in items for value in (match.player1_id, match.player2_id)})
                return SuccessResponse(data=[self._match_summary(match, tournaments[match.tournament_id], players) for match in items if tournaments.get(match.tournament_id)])

        return await self._cached('matches:upcoming', SuccessResponse[list[MatchSummary]], loader, ttl_seconds=settings.cache.live_ttl_seconds)

    async def get_match_results(self):
        async def loader() -> SuccessResponse[list[MatchSummary]]:
            async with db_session_manager.session() as session:
                items = await self.matches.get_results(session)
                tournaments = {match.tournament_id: await self.tournaments.get(session, match.tournament_id) for match in items}
                players = await self._players_map(session, {value for match in items for value in (match.player1_id, match.player2_id)})
                return SuccessResponse(data=[self._match_summary(match, tournaments[match.tournament_id], players) for match in items if tournaments.get(match.tournament_id)])

        return await self._cached('matches:results', SuccessResponse[list[MatchSummary]], loader)

    async def list_news(self, page: int, per_page: int):
        async def loader() -> PaginatedResponse[NewsArticleSummary]:
            async with db_session_manager.session() as session:
                items, total = await self.news.list(session, page=page, per_page=per_page)
                categories = {category.id: category for category in await self.news.list_categories(session)}
                data = [self._news_summary(item, categories.get(item.category_id)) for item in items]
                return PaginatedResponse(data=data, meta=self._paginate_meta(page, per_page, total))

        return await self._cached(f'news:list:{page}:{per_page}', PaginatedResponse[NewsArticleSummary], loader)

    async def get_news_categories(self):
        async def loader() -> SuccessResponse[list[NewsCategoryItem]]:
            async with db_session_manager.session() as session:
                categories = await self.news.list_categories(session)
                return SuccessResponse(data=[NewsCategoryItem(id=item.id, slug=item.slug, name=item.name) for item in categories])

        return await self._cached('news:categories', SuccessResponse[list[NewsCategoryItem]], loader)

    async def get_news_tags(self):
        async def loader() -> SuccessResponse[list[TagItem]]:
            async with db_session_manager.session() as session:
                tags = await self.news.list_tags(session)
                return SuccessResponse(data=[TagItem(id=item.id, slug=item.slug, name=item.name) for item in tags])

        return await self._cached('news:tags', SuccessResponse[list[TagItem]], loader)

    async def get_featured_news(self):
        async def loader() -> SuccessResponse[list[NewsArticleSummary]]:
            async with db_session_manager.session() as session:
                items = await self.news.list_featured(session)
                categories = {category.id: category for category in await self.news.list_categories(session)}
                return SuccessResponse(data=[self._news_summary(item, categories.get(item.category_id)) for item in items])

        return await self._cached('news:featured', SuccessResponse[list[NewsArticleSummary]], loader)

    async def get_related_news(self, slug: str | None = None):
        async def loader() -> SuccessResponse[list[NewsArticleSummary]]:
            async with db_session_manager.session() as session:
                items = await self.news.list_related(session, slug=slug)
                categories = {category.id: category for category in await self.news.list_categories(session)}
                return SuccessResponse(data=[self._news_summary(item, categories.get(item.category_id)) for item in items])

        return await self._cached(f'news:related:{slug or ""}', SuccessResponse[list[NewsArticleSummary]], loader)

    async def get_news_article(self, slug: str):
        async def loader() -> SuccessResponse[NewsArticleDetail]:
            async with db_session_manager.session() as session:
                article = await self.news.get_by_slug(session, slug)
                if article is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Article not found')
                categories = {category.id: category for category in await self.news.list_categories(session)}
                related = await self.news.list_related(session, slug=slug)
                data = NewsArticleDetail(**self._news_summary(article, categories.get(article.category_id)).model_dump(), content_html=article.content_html, seo_title=article.seo_title, seo_description=article.seo_description, related_news=[self._news_summary(item, categories.get(item.category_id)) for item in related])
                return SuccessResponse(data=data)

        return await self._cached(f'news:detail:{slug}', SuccessResponse[NewsArticleDetail], loader)
