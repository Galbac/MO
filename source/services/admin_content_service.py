from __future__ import annotations

import re

from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, status

from source.db.session import db_session_manager
from source.repositories import AuditRepository, MatchRepository, NewsRepository, PlayerRepository, TournamentRepository
from source.schemas.pydantic.auth import MessageResponse, SimpleMessage
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.match import MatchEventCreateRequest, MatchEventItem, MatchScoreUpdateRequest, MatchStatsUpdateRequest, MatchStatusUpdateRequest
from source.schemas.pydantic.news import NewsArticleCreateRequest, NewsStatusRequest
from source.services.cache_service import CacheService
from source.services.job_service import JobService
from source.services.live_hub import live_hub
from source.services.portal_query_service import PortalQueryService
from source.services.workflow_service import WorkflowService


class AdminContentService:
    def __init__(self) -> None:
        self.players = PlayerRepository()
        self.tournaments = TournamentRepository()
        self.matches = MatchRepository()
        self.news = NewsRepository()
        self.audit = AuditRepository()
        self.query = PortalQueryService()
        self.cache = CacheService()
        self.jobs = JobService()
        self.workflows = WorkflowService()

    @staticmethod
    def _require(payload: dict[str, Any], field: str, current: Any = None) -> Any:
        value = payload.get(field, current)
        if value in (None, ''):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'{field} is required')
        return value

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if isinstance(value, date):
            return value
        if value in (None, ''):
            return None
        return date.fromisoformat(str(value))

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if value in (None, ''):
            return None
        return datetime.fromisoformat(str(value))

    @classmethod
    def _player_payload(cls, payload: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
        current = current or {}
        return {
            'slug': cls._require(payload, 'slug', current.get('slug')),
            'first_name': cls._require(payload, 'first_name', current.get('first_name')),
            'last_name': cls._require(payload, 'last_name', current.get('last_name')),
            'full_name': cls._require(payload, 'full_name', current.get('full_name')),
            'country_code': cls._require(payload, 'country_code', current.get('country_code')),
            'country_name': payload.get('country_name', current.get('country_name')),
            'birth_date': cls._parse_date(payload.get('birth_date', current.get('birth_date'))),
            'height_cm': int(payload['height_cm']) if payload.get('height_cm') not in (None, '') else current.get('height_cm'),
            'weight_kg': int(payload['weight_kg']) if payload.get('weight_kg') not in (None, '') else current.get('weight_kg'),
            'hand': payload.get('hand', current.get('hand')),
            'backhand': payload.get('backhand', current.get('backhand')),
            'biography': payload.get('biography', current.get('biography')),
            'photo_url': payload.get('photo_url', current.get('photo_url')),
            'status': payload.get('status', current.get('status', 'active')),
            'current_rank': int(payload['current_rank']) if payload.get('current_rank') not in (None, '') else current.get('current_rank'),
            'current_points': int(payload['current_points']) if payload.get('current_points') not in (None, '') else current.get('current_points'),
        }

    @classmethod
    def _tournament_payload(cls, payload: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
        current = current or {}
        return {
            'slug': cls._require(payload, 'slug', current.get('slug')),
            'name': cls._require(payload, 'name', current.get('name')),
            'short_name': payload.get('short_name', current.get('short_name')),
            'category': cls._require(payload, 'category', current.get('category')),
            'surface': cls._require(payload, 'surface', current.get('surface')),
            'indoor': bool(payload.get('indoor', current.get('indoor', False))),
            'city': payload.get('city', current.get('city')),
            'country_code': payload.get('country_code', current.get('country_code')),
            'prize_money': payload.get('prize_money', current.get('prize_money')),
            'points_winner': int(payload['points_winner']) if payload.get('points_winner') not in (None, '') else current.get('points_winner'),
            'season_year': int(cls._require(payload, 'season_year', current.get('season_year'))),
            'start_date': cls._parse_date(payload.get('start_date', current.get('start_date'))),
            'end_date': cls._parse_date(payload.get('end_date', current.get('end_date'))),
            'status': payload.get('status', current.get('status', 'scheduled')),
            'logo_url': payload.get('logo_url', current.get('logo_url')),
            'description': payload.get('description', current.get('description')),
        }

    @classmethod
    def _match_payload(cls, payload: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
        current = current or {}
        return {
            'slug': cls._require(payload, 'slug', current.get('slug')),
            'tournament_id': int(cls._require(payload, 'tournament_id', current.get('tournament_id'))),
            'round_code': payload.get('round_code', current.get('round_code')),
            'best_of_sets': int(payload.get('best_of_sets', current.get('best_of_sets', 3))),
            'player1_id': int(cls._require(payload, 'player1_id', current.get('player1_id'))),
            'player2_id': int(cls._require(payload, 'player2_id', current.get('player2_id'))),
            'winner_id': int(payload['winner_id']) if payload.get('winner_id') not in (None, '') else current.get('winner_id'),
            'status': payload.get('status', current.get('status', 'scheduled')),
            'scheduled_at': cls._parse_datetime(cls._require(payload, 'scheduled_at', current.get('scheduled_at'))),
            'actual_start_at': cls._parse_datetime(payload.get('actual_start_at', current.get('actual_start_at'))),
            'actual_end_at': cls._parse_datetime(payload.get('actual_end_at', current.get('actual_end_at'))),
            'court_name': payload.get('court_name', current.get('court_name')),
            'score_summary': payload.get('score_summary', current.get('score_summary')),
            'retire_reason': payload.get('retire_reason', current.get('retire_reason')),
            'walkover_reason': payload.get('walkover_reason', current.get('walkover_reason')),
        }

    @staticmethod
    def _sanitize_html(value: str) -> str:
        sanitized = re.sub(r'<\s*script[^>]*>.*?<\s*/\s*script\s*>', '', value, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r"on[a-zA-Z]+\s*=\s*(\".*?\"|'[^']*'|[^\s>]+)", '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
        return sanitized.strip()

    @classmethod
    def _news_payload(cls, payload: NewsArticleCreateRequest, current: dict[str, Any] | None = None) -> dict[str, Any]:
        current = current or {}
        raw = payload.model_dump()
        return {
            'slug': cls._require(raw, 'slug', current.get('slug')),
            'title': cls._require(raw, 'title', current.get('title')),
            'subtitle': raw.get('subtitle', current.get('subtitle')),
            'lead': raw.get('lead', current.get('lead')),
            'content_html': cls._sanitize_html(cls._require(raw, 'content_html', current.get('content_html'))),
            'cover_image_url': raw.get('cover_image_url', current.get('cover_image_url')),
            'author_id': current.get('author_id'),
            'category_id': raw.get('category_id', current.get('category_id')),
            'status': raw.get('status', current.get('status', 'draft')),
            'seo_title': raw.get('seo_title', current.get('seo_title')),
            'seo_description': raw.get('seo_description', current.get('seo_description')),
            'published_at': current.get('published_at'),
        }

    @staticmethod
    def _entity_dict(entity) -> dict[str, Any]:
        return {column.name: getattr(entity, column.name) for column in entity.__table__.columns}

    async def _log_audit(self, *, action: str, entity_type: str, entity_id: int | None, before_json: dict | None, after_json: dict | None, user_id: int | None) -> None:
        async with db_session_manager.session() as session:
            await self.audit.create(session, {'user_id': user_id, 'action': action, 'entity_type': entity_type, 'entity_id': entity_id, 'before_json': before_json, 'after_json': after_json})

    def _invalidate_cache(self, *prefixes: str) -> None:
        self.cache.invalidate_prefixes(*prefixes)

    async def _broadcast_match_update(self, match_id: int, event_name: str, extra: dict[str, Any] | None = None) -> None:
        try:
            detail = (await self.query.get_match(match_id)).data
        except HTTPException:
            return
        channels = {
            'live:all',
            f'live:match:{match_id}',
        }
        if detail.tournament_id is not None:
            channels.add(f'live:tournament:{detail.tournament_id}')
        if detail.player1_id is not None:
            channels.add(f'live:player:{detail.player1_id}')
        if detail.player2_id is not None:
            channels.add(f'live:player:{detail.player2_id}')
        payload = {
            'event': event_name,
            'match_id': match_id,
            'tournament_id': detail.tournament_id,
            'player_ids': [detail.player1_id, detail.player2_id],
            'data': detail.model_dump(),
        }
        if extra:
            payload['meta'] = extra
        await live_hub.broadcast(channels=channels, payload=payload)

    @staticmethod
    def _decide_winner(match, sets: list[Any]) -> int | None:
        if match.status == 'retired':
            if match.winner_id:
                return match.winner_id
            return match.player2_id if match.retire_reason and match.player1_id else None
        if match.status == 'walkover':
            return match.winner_id
        player1_sets = sum(1 for item in sets if item.player1_games > item.player2_games)
        player2_sets = sum(1 for item in sets if item.player2_games > item.player1_games)
        if player1_sets == player2_sets:
            return match.winner_id
        return match.player1_id if player1_sets > player2_sets else match.player2_id

    async def list_admin_players(self):
        payload = await self.query.list_players(None, None, None, None, None, None, 1, 100)
        return SuccessResponse(data=payload.data)

    async def create_admin_player(self, payload: dict[str, Any], actor_id: int | None = None):
        async with db_session_manager.session() as session:
            player = await self.players.create(session, self._player_payload(payload))
            after = self._entity_dict(player)
        await self._log_audit(action='player.create', entity_type='player', entity_id=player.id, before_json=None, after_json=after, user_id=actor_id)
        self._invalidate_cache('players:', 'matches:', 'live:', 'search:')
        return await self.query.get_player(player.id)

    async def get_admin_player(self, player_id: int):
        return await self.query.get_player(player_id)

    async def update_admin_player(self, player_id: int, payload: dict[str, Any], actor_id: int | None = None):
        async with db_session_manager.session() as session:
            player = await self.players.get(session, player_id)
            if player is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Player not found')
            before = self._entity_dict(player)
            updated = await self.players.update(session, player, self._player_payload(payload, before))
            after = self._entity_dict(updated)
        await self._log_audit(action='player.update', entity_type='player', entity_id=player_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('players:', 'matches:', 'live:', 'search:')
        return await self.query.get_player(player_id)

    async def delete_admin_player(self, player_id: int, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            player = await self.players.get(session, player_id)
            if player is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Player not found')
            before = self._entity_dict(player)
            await self.players.delete(session, player)
        await self._log_audit(action='player.delete', entity_type='player', entity_id=player_id, before_json=before, after_json=None, user_id=actor_id)
        self._invalidate_cache('players:', 'matches:', 'live:', 'search:')
        return MessageResponse(data=SimpleMessage(message='Player deleted'))

    async def list_admin_tournaments(self):
        payload = await self.query.list_tournaments(1, 100)
        return SuccessResponse(data=payload.data)

    async def create_admin_tournament(self, payload: dict[str, Any], actor_id: int | None = None):
        async with db_session_manager.session() as session:
            tournament = await self.tournaments.create(session, self._tournament_payload(payload))
            after = self._entity_dict(tournament)
        await self._log_audit(action='tournament.create', entity_type='tournament', entity_id=tournament.id, before_json=None, after_json=after, user_id=actor_id)
        self._invalidate_cache('tournaments:', 'matches:', 'live:', 'news:', 'search:')
        return await self.query.get_tournament(tournament.id)

    async def get_admin_tournament(self, tournament_id: int):
        return await self.query.get_tournament(tournament_id)

    async def update_admin_tournament(self, tournament_id: int, payload: dict[str, Any], actor_id: int | None = None):
        async with db_session_manager.session() as session:
            tournament = await self.tournaments.get(session, tournament_id)
            if tournament is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tournament not found')
            before = self._entity_dict(tournament)
            updated = await self.tournaments.update(session, tournament, self._tournament_payload(payload, before))
            after = self._entity_dict(updated)
        await self._log_audit(action='tournament.update', entity_type='tournament', entity_id=tournament_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('tournaments:', 'matches:', 'live:', 'news:', 'search:')
        return await self.query.get_tournament(tournament_id)

    async def delete_admin_tournament(self, tournament_id: int, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            tournament = await self.tournaments.get(session, tournament_id)
            if tournament is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tournament not found')
            before = self._entity_dict(tournament)
            await self.tournaments.delete(session, tournament)
        await self._log_audit(action='tournament.delete', entity_type='tournament', entity_id=tournament_id, before_json=before, after_json=None, user_id=actor_id)
        self._invalidate_cache('tournaments:', 'matches:', 'live:', 'news:', 'search:')
        return MessageResponse(data=SimpleMessage(message='Tournament deleted'))

    async def list_admin_matches(self):
        payload = await self.query.list_matches(1, 100, None)
        return SuccessResponse(data=payload.data)

    async def create_admin_match(self, payload: dict[str, Any], actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.create(session, self._match_payload(payload))
            after = self._entity_dict(match)
        await self._log_audit(action='match.create', entity_type='match', entity_id=match.id, before_json=None, after_json=after, user_id=actor_id)
        self._invalidate_cache('matches:', 'players:', 'tournaments:', 'live:', 'search:')
        return await self.query.get_match(match.id)

    async def get_admin_match(self, match_id: int):
        return await self.query.get_match(match_id)

    async def update_admin_match(self, match_id: int, payload: dict[str, Any], actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            before = self._entity_dict(match)
            updated = await self.matches.update(session, match, self._match_payload(payload, before))
            after = self._entity_dict(updated)
        await self._log_audit(action='match.update', entity_type='match', entity_id=match_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('matches:', 'players:', 'tournaments:', 'live:', 'search:')
        if before.get('status') != after.get('status') and after.get('status') in {'about_to_start', 'live'}:
            await self.workflows.process_match_status_change(match_id, str(after.get('status')))
        await self._broadcast_match_update(match_id, 'match_status_changed', {'status': after.get('status')})
        return await self.query.get_match(match_id)

    async def delete_admin_match(self, match_id: int, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            before = self._entity_dict(match)
            await self.matches.delete(session, match)
        await self._log_audit(action='match.delete', entity_type='match', entity_id=match_id, before_json=before, after_json=None, user_id=actor_id)
        self._invalidate_cache('matches:', 'players:', 'tournaments:', 'live:', 'search:')
        return MessageResponse(data=SimpleMessage(message='Match deleted'))

    async def update_admin_match_status(self, match_id: int, payload: MatchStatusUpdateRequest, actor_id: int | None = None):
        return await self.update_admin_match(match_id, {'status': payload.status}, actor_id=actor_id)

    async def update_admin_match_score(self, match_id: int, payload: MatchScoreUpdateRequest, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            before = self._entity_dict(match)
            updated = await self.matches.update(session, match, {'score_summary': payload.score_summary})
            if payload.sets:
                await self.matches.replace_sets(session, match_id, [item.model_dump() for item in payload.sets])
            after = self._entity_dict(updated)
        await self._log_audit(action='match.update_score', entity_type='match', entity_id=match_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('matches:', 'players:', 'tournaments:', 'live:')
        await self._broadcast_match_update(match_id, 'score_updated', {'score_summary': payload.score_summary})
        return await self.query.get_match(match_id)

    async def update_admin_match_stats(self, match_id: int, payload: MatchStatsUpdateRequest, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            await self.matches.upsert_stats(session, match_id, payload.stats.model_dump())
        await self._log_audit(action='match.update_stats', entity_type='match', entity_id=match_id, before_json=None, after_json=payload.stats.model_dump(), user_id=actor_id)
        self._invalidate_cache('matches:', 'live:')
        await self._broadcast_match_update(match_id, 'stats_updated', payload.stats.model_dump())
        return await self.query.get_match(match_id)

    async def create_admin_match_event(self, match_id: int, payload: MatchEventCreateRequest, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            event = await self.matches.create_event(session, {'match_id': match_id, 'event_type': payload.event_type, 'set_number': payload.set_number, 'game_number': payload.game_number, 'player_id': payload.player_id, 'payload_json': payload.payload_json, 'created_at': datetime.now(tz=UTC)})
        await self._log_audit(action='match.create_event', entity_type='match', entity_id=match_id, before_json=None, after_json={'event_id': event.id, **payload.model_dump()}, user_id=actor_id)
        self._invalidate_cache('matches:', 'live:')
        broadcast_event = payload.event_type if payload.event_type in {'break_point', 'set_finished', 'match_finished'} else 'point_updated'
        await self._broadcast_match_update(match_id, broadcast_event, {'event_id': event.id, **payload.model_dump()})
        return SuccessResponse(data=MatchEventItem(id=event.id, event_type=event.event_type, set_number=event.set_number, game_number=event.game_number, player_id=event.player_id, payload_json=event.payload_json or {}, created_at=event.created_at))

    async def finalize_admin_match(self, match_id: int, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            before = self._entity_dict(match)
            sets = await self.matches.get_sets(session, match_id)
            winner_id = self._decide_winner(match, sets)
            updated = await self.matches.update(session, match, {'status': 'finished', 'winner_id': winner_id, 'actual_end_at': datetime.now(tz=UTC)})
            after = self._entity_dict(updated)
        await self._log_audit(action='match.finalize', entity_type='match', entity_id=match_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('matches:', 'players:', 'tournaments:', 'live:', 'rankings:')
        await self._broadcast_match_update(match_id, 'match_finished', {'winner_id': winner_id})
        await self.jobs.enqueue(job_type='finalize_match_postprocess', payload={'match_id': match_id, 'actor_id': actor_id})
        await self.jobs.process_due_jobs()
        return MessageResponse(data=SimpleMessage(message='Match finalized and post-processing queued'))

    async def reopen_admin_match(self, match_id: int, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            before = self._entity_dict(match)
            updated = await self.matches.update(session, match, {'status': 'scheduled', 'actual_end_at': None})
            after = self._entity_dict(updated)
        await self._log_audit(action='match.reopen', entity_type='match', entity_id=match_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('matches:', 'players:', 'tournaments:', 'live:')
        await self._broadcast_match_update(match_id, 'match_status_changed', {'status': 'scheduled'})
        return MessageResponse(data=SimpleMessage(message='Match reopened'))

    async def list_admin_news(self):
        payload = await self.query.list_news(1, 100)
        return SuccessResponse(data=payload.data)

    async def create_admin_news(self, payload: NewsArticleCreateRequest, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            article = await self.news.create(session, self._news_payload(payload))
            after = self._entity_dict(article)
        await self._log_audit(action='news.create', entity_type='news', entity_id=article.id, before_json=None, after_json=after, user_id=actor_id)
        self._invalidate_cache('news:', 'search:', 'players:', 'tournaments:')
        return await self.query.get_news_article(article.slug)

    async def get_admin_news(self, news_id: int):
        async with db_session_manager.session() as session:
            article = await self.news.get(session, news_id)
            if article is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='News not found')
            return await self.query.get_news_article(article.slug)

    async def update_admin_news(self, news_id: int, payload: NewsArticleCreateRequest, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            article = await self.news.get(session, news_id)
            if article is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='News not found')
            before = self._entity_dict(article)
            updated = await self.news.update(session, article, self._news_payload(payload, before))
            after = self._entity_dict(updated)
        await self._log_audit(action='news.update', entity_type='news', entity_id=news_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('news:', 'search:', 'players:', 'tournaments:')
        return await self.query.get_news_article(updated.slug)

    async def delete_admin_news(self, news_id: int, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            article = await self.news.get(session, news_id)
            if article is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='News not found')
            before = self._entity_dict(article)
            await self.news.delete(session, article)
        await self._log_audit(action='news.delete', entity_type='news', entity_id=news_id, before_json=before, after_json=None, user_id=actor_id)
        self._invalidate_cache('news:', 'search:', 'players:', 'tournaments:')
        return MessageResponse(data=SimpleMessage(message='News deleted'))

    async def update_admin_news_status(self, news_id: int, payload: NewsStatusRequest, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            article = await self.news.get(session, news_id)
            if article is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='News not found')
            before = self._entity_dict(article)
            publish_at = datetime.fromisoformat(payload.publish_at) if payload.publish_at else (datetime.now(tz=UTC) if payload.status == 'published' else article.published_at)
            updated = await self.news.update(session, article, {'status': payload.status, 'published_at': publish_at})
            after = self._entity_dict(updated)
        await self._log_audit(action='news.update_status', entity_type='news', entity_id=news_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('news:', 'search:', 'players:', 'tournaments:')
        return await self.query.get_news_article(updated.slug)

    async def publish_admin_news(self, news_id: int, actor_id: int | None = None):
        await self.update_admin_news_status(news_id, NewsStatusRequest(status='published', publish_at=None), actor_id=actor_id)
        return MessageResponse(data=SimpleMessage(message='News published'))

    async def schedule_admin_news(self, news_id: int, payload: NewsStatusRequest, actor_id: int | None = None):
        if not payload.publish_at:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='publish_at is required')
        await self.update_admin_news_status(news_id, NewsStatusRequest(status='scheduled', publish_at=payload.publish_at), actor_id=actor_id)
        await self.jobs.enqueue(job_type='publish_scheduled_news', payload={'news_id': news_id}, run_at=datetime.fromisoformat(payload.publish_at))
        return MessageResponse(data=SimpleMessage(message=f'News scheduled for {payload.publish_at}'))

    async def attach_admin_news_tags(self, news_id: int):
        async with db_session_manager.session() as session:
            article = await self.news.get(session, news_id)
            if article is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='News not found')
        return SuccessResponse(data=[])
