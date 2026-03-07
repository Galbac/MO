from __future__ import annotations

import re

from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, status

from source.db.session import db_session_manager
from source.repositories import AuditRepository, MatchRepository, NewsRepository, PlayerRepository, TournamentRepository
from source.schemas.pydantic.admin import AdminActionResult, AdminBulkImportResult
from source.schemas.pydantic.common import SuccessResponse
from source.schemas.pydantic.match import MatchEventCreateRequest, MatchEventItem, MatchScoreUpdateRequest, MatchStatsUpdateRequest, MatchStatusUpdateRequest
from source.schemas.pydantic.news import NewsArticleCreateRequest, NewsStatusRequest, TagItem
from source.services.cache_service import CacheService
from source.services.job_service import JobService
from source.services.live_hub import live_hub
from source.services.portal_query_service import PortalQueryService
from source.services.workflow_service import WorkflowService
from source.services.runtime_state_store import RuntimeStateStore


class AdminContentService:
    VALID_MATCH_STATUSES = {
        'scheduled',
        'about_to_start',
        'live',
        'suspended',
        'interrupted',
        'finished',
        'retired',
        'walkover',
        'cancelled',
        'postponed',
    }
    COMPLETED_MATCH_STATUSES = {'finished', 'retired', 'walkover'}
    TERMINAL_MATCH_STATUSES = COMPLETED_MATCH_STATUSES | {'cancelled', 'postponed'}
    MATCH_STATUS_TRANSITIONS = {
        'scheduled': {'about_to_start', 'live', 'postponed', 'cancelled'},
        'about_to_start': {'scheduled', 'live', 'postponed', 'cancelled'},
        'live': {'about_to_start', 'suspended', 'interrupted', 'finished', 'retired', 'walkover', 'cancelled'},
        'suspended': {'live', 'interrupted', 'postponed', 'cancelled'},
        'interrupted': {'live', 'postponed', 'cancelled'},
        'postponed': {'scheduled', 'about_to_start', 'cancelled'},
        'cancelled': set(),
        'finished': set(),
        'retired': set(),
        'walkover': set(),
    }
    VALID_NEWS_STATUSES = {'draft', 'review', 'scheduled', 'published', 'archived'}
    NEWS_STATUS_TRANSITIONS = {
        'draft': {'review', 'scheduled', 'published', 'archived'},
        'review': {'draft', 'scheduled', 'published', 'archived'},
        'scheduled': {'draft', 'review', 'published', 'archived'},
        'published': {'archived'},
        'archived': {'draft'},
    }

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
        self.store = RuntimeStateStore()
        self.news_tags_namespace = "news_tags"

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

    @staticmethod
    def _action_result(
        *,
        entity_type: str,
        action: str,
        status: str = 'ok',
        entity_id: int | None = None,
        message: str | None = None,
        job_id: int | None = None,
        scheduled_at: datetime | None = None,
        details: dict[str, Any] | None = None,
    ) -> SuccessResponse[AdminActionResult]:
        return SuccessResponse(
            data=AdminActionResult(
                entity_type=entity_type,
                action=action,
                status=status,
                entity_id=entity_id,
                message=message,
                job_id=job_id,
                scheduled_at=scheduled_at,
                details=details or {},
            )
        )

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
        sanitized = value
        for tag in ('script', 'iframe', 'object', 'embed', 'style', 'link', 'meta', 'base', 'form', 'input', 'button', 'textarea', 'select'):
            sanitized = re.sub(rf'<\s*{tag}[^>]*>.*?<\s*/\s*{tag}\s*>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
            sanitized = re.sub(rf'<\s*{tag}[^>]*/?\s*>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r"on[a-zA-Z]+\s*=\s*(\".*?\"|'[^']*'|[^\s>]+)", '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r"style\s*=\s*(\".*?\"|'[^']*'|[^\s>]+)", '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r"srcdoc\s*=\s*(\".*?\"|'[^']*'|[^\s>]+)", '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'(javascript:|data:text/html)', '', sanitized, flags=re.IGNORECASE)
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


    def _news_tag_mapping(self) -> dict[str, list[int]]:
        payload = self.store.read_namespace(self.news_tags_namespace, {})
        return payload if isinstance(payload, dict) else {}

    def _save_news_tag_mapping(self, payload: dict[str, list[int]]) -> None:
        self.store.write_namespace(self.news_tags_namespace, payload)

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

    @classmethod
    def _normalize_match_status(cls, value: str) -> str:
        normalized = str(value or '').strip().lower()
        if normalized not in cls.VALID_MATCH_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Недопустимый статус матча.',
            )
        return normalized

    @classmethod
    def _ensure_match_transition(cls, current_status: str, new_status: str) -> str:
        current = cls._normalize_match_status(current_status)
        target = cls._normalize_match_status(new_status)
        if current == target:
            return target
        if target not in cls.MATCH_STATUS_TRANSITIONS.get(current, set()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f'Переход статуса матча "{current}" -> "{target}" запрещен.',
            )
        return target

    @classmethod
    def _normalize_news_status(cls, value: str) -> str:
        normalized = str(value or '').strip().lower()
        if normalized not in cls.VALID_NEWS_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Недопустимый статус новости.',
            )
        return normalized

    @classmethod
    def _ensure_news_transition(cls, current_status: str, new_status: str) -> str:
        current = cls._normalize_news_status(current_status)
        target = cls._normalize_news_status(new_status)
        if current == target:
            return target
        if target not in cls.NEWS_STATUS_TRANSITIONS.get(current, set()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f'Переход статуса новости "{current}" -> "{target}" запрещен.',
            )
        return target

    @staticmethod
    def _validate_match_participants(payload: dict[str, Any]) -> None:
        if int(payload['player1_id']) == int(payload['player2_id']):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='У матча должны быть два разных игрока.',
            )
        winner_id = payload.get('winner_id')
        if winner_id is not None and int(winner_id) not in {int(payload['player1_id']), int(payload['player2_id'])}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Победитель должен быть одним из участников матча.',
            )

    @staticmethod
    def _validate_score_payload(payload: MatchScoreUpdateRequest, *, best_of_sets: int) -> None:
        if payload.sets and len(payload.sets) > best_of_sets:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Количество сетов превышает формат матча.',
            )
        if not payload.sets:
            return
        actual_tokens = re.findall(r'\d+-\d+', str(payload.score_summary))
        expected_tokens = [f'{item.player1_games}-{item.player2_games}' for item in payload.sets]
        if actual_tokens[:len(expected_tokens)] != expected_tokens:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Сводный счет не совпадает с переданными сетами.',
            )

    @classmethod
    def _resolve_finalize_status(cls, current_status: str) -> str:
        normalized = cls._normalize_match_status(current_status)
        if normalized in {'cancelled', 'postponed'}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Отмененный или перенесенный матч нельзя финализировать.',
            )
        if normalized in {'retired', 'walkover'}:
            return normalized
        return 'finished'

    @staticmethod
    def _decide_winner(match, sets: list[Any], *, target_status: str | None = None) -> int | None:
        status_value = target_status or match.status
        if status_value == 'retired':
            if match.winner_id:
                return match.winner_id
            return match.player2_id if getattr(match, 'retire_reason', None) and getattr(match, 'player1_id', None) else None
        if status_value == 'walkover':
            return match.winner_id
        player1_sets = sum(1 for item in sets if item.player1_games > item.player2_games)
        player2_sets = sum(1 for item in sets if item.player2_games > item.player1_games)
        if player1_sets == player2_sets:
            return match.winner_id
        return match.player1_id if player1_sets > player2_sets else match.player2_id

    async def list_admin_players(self, *, search: str | None = None, country_code: str | None = None, hand: str | None = None, status: str | None = None):
        payload = await self.query.list_players(search, country_code, hand, status, None, None, 1, 100)
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
        return self._action_result(entity_type='player', action='delete', entity_id=player_id, message='Player deleted')


    async def import_admin_players(self, payload: dict[str, Any], actor_id: int | None = None):
        rows = payload.get('players') if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='players is required')
        imported = 0
        updated_ids: list[int] = []
        async with db_session_manager.session() as session:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                normalized = self._player_payload(row)
                existing = await self.players.get_by_slug(session, normalized['slug'])
                if existing is None:
                    item = await self.players.create(session, normalized)
                else:
                    item = await self.players.update(session, existing, normalized)
                updated_ids.append(item.id)
                imported += 1
        await self._log_audit(action='player.import', entity_type='player', entity_id=None, before_json=None, after_json={'count': imported, 'player_ids': updated_ids}, user_id=actor_id)
        self._invalidate_cache('players:', 'matches:', 'live:', 'search:')
        return SuccessResponse(
            data=AdminBulkImportResult(
                entity_type='player',
                action='import',
                status='ok',
                imported_count=imported,
                entity_ids=updated_ids,
                message=f'Imported {imported} players',
                details={'message': f'Imported {imported} players'},
            )
        )

    async def upload_admin_player_photo(self, player_id: int, payload: dict[str, Any], actor_id: int | None = None):
        photo_url = str(payload.get('photo_url') or '').strip()
        if not photo_url:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='photo_url is required')
        async with db_session_manager.session() as session:
            player = await self.players.get(session, player_id)
            if player is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Player not found')
            before = self._entity_dict(player)
            updated = await self.players.update(session, player, {'photo_url': photo_url})
            after = self._entity_dict(updated)
        await self._log_audit(action='player.photo.update', entity_type='player', entity_id=player_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('players:', 'matches:', 'live:', 'search:')
        return self._action_result(entity_type='player', action='photo.update', entity_id=player_id, message='Player photo updated', details={'photo_url': photo_url})

    async def recalculate_admin_player_stats(self, player_id: int, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            player = await self.players.get(session, player_id)
            if player is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Player not found')
        job = await self.jobs.enqueue(job_type='recalculate_player_stats', payload={'player_ids': [player_id]})
        await self.jobs.process_due_jobs()
        await self._log_audit(action='player.recalculate_stats', entity_type='player', entity_id=player_id, before_json=None, after_json={'job_id': job['id']}, user_id=actor_id)
        self._invalidate_cache('players:', 'matches:', 'live:', 'search:')
        current_job = next(item for item in self.jobs.list_jobs() if int(item['id']) == int(job['id']))
        return self._action_result(
            entity_type='player',
            action='recalculate_stats',
            entity_id=player_id,
            message=f'Player stats recalculated via job {job["id"]}',
            job_id=int(job['id']),
            status=str(current_job.get('status') or 'pending'),
            details=current_job.get('result') or {},
        )

    async def list_admin_tournaments(self, *, search: str | None = None, category: str | None = None, surface: str | None = None, status: str | None = None, season_year: int | None = None):
        if all(value is None for value in (search, category, surface, status, season_year)):
            payload = await self.query.list_tournaments(1, 100)
            return SuccessResponse(data=payload.data)
        async with db_session_manager.session() as session:
            items, _ = await self.tournaments.list(session, page=1, per_page=100, search=search, category=category, surface=surface, status=status, season_year=season_year)
        return SuccessResponse(data=[self.query._tournament_summary(item) for item in items])

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
        if before.get('status') != after.get('status') and after.get('status') == 'live':
            await self.workflows.process_tournament_status_change(tournament_id, 'live')
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
        return self._action_result(entity_type='tournament', action='delete', entity_id=tournament_id, message='Tournament deleted')

    async def generate_admin_tournament_draw(self, tournament_id: int, actor_id: int | None = None):
        result = await self.workflows.generate_tournament_draw_snapshot(tournament_id)
        await self._log_audit(action='tournament.draw.generate', entity_type='tournament', entity_id=tournament_id, before_json=None, after_json=result, user_id=actor_id)
        return self._action_result(entity_type='tournament', action='draw.generate', entity_id=tournament_id, message=f"Draw generated with {result['matches']} matches", details=result)

    async def publish_admin_tournament(self, tournament_id: int, actor_id: int | None = None):
        await self.update_admin_tournament(tournament_id, {'status': 'published'}, actor_id=actor_id)
        await self._log_audit(action='tournament.publish', entity_type='tournament', entity_id=tournament_id, before_json=None, after_json={'status': 'published'}, user_id=actor_id)
        return self._action_result(entity_type='tournament', action='publish', entity_id=tournament_id, message='Tournament published', details={'status': 'published'})

    async def list_admin_matches(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        tournament_id: int | None = None,
        player_id: int | None = None,
        round_code: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        async with db_session_manager.session() as session:
            items, _total = await self.matches.list(
                session,
                page=1,
                per_page=100,
                status=status,
                tournament_id=tournament_id,
                player_id=player_id,
                round_code=round_code,
                search=search,
                date_from=date.fromisoformat(date_from) if date_from else None,
                date_to=date.fromisoformat(date_to) if date_to else None,
            )
            tournaments = {match.tournament_id: await self.tournaments.get(session, match.tournament_id) for match in items}
            player_ids = {value for match in items for value in (match.player1_id, match.player2_id)}
            players = await self.query._players_map(session, player_ids)
            data = [self.query._match_summary(match, tournaments[match.tournament_id], players) for match in items if tournaments.get(match.tournament_id)]
        return SuccessResponse(data=data)

    async def create_admin_match(self, payload: dict[str, Any], actor_id: int | None = None):
        normalized_payload = self._match_payload(payload)
        normalized_payload['status'] = self._normalize_match_status(str(normalized_payload.get('status') or 'scheduled'))
        self._validate_match_participants(normalized_payload)
        async with db_session_manager.session() as session:
            match = await self.matches.create(session, normalized_payload)
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
            normalized_payload = self._match_payload(payload, before)
            normalized_payload['status'] = self._ensure_match_transition(str(before.get('status') or 'scheduled'), str(normalized_payload.get('status') or before.get('status') or 'scheduled'))
            self._validate_match_participants(normalized_payload)
            updated = await self.matches.update(session, match, normalized_payload)
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
        return self._action_result(entity_type='match', action='delete', entity_id=match_id, message='Match deleted')

    async def update_admin_match_status(self, match_id: int, payload: MatchStatusUpdateRequest, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            before = self._entity_dict(match)
            target_status = self._ensure_match_transition(str(match.status or 'scheduled'), payload.status)
            update_payload: dict[str, Any] = {'status': target_status}
            if target_status == 'live' and match.actual_start_at is None:
                update_payload['actual_start_at'] = datetime.now(tz=UTC)
            if target_status not in {'retired', 'walkover'}:
                update_payload.setdefault('retire_reason', None)
                update_payload.setdefault('walkover_reason', None)
            updated = await self.matches.update(session, match, update_payload)
            after = self._entity_dict(updated)
        await self._log_audit(action='match.update_status', entity_type='match', entity_id=match_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('matches:', 'players:', 'tournaments:', 'live:', 'search:')
        if before.get('status') != after.get('status') and after.get('status') in {'about_to_start', 'live'}:
            await self.workflows.process_match_status_change(match_id, str(after.get('status')))
        await self._broadcast_match_update(match_id, 'match_status_changed', {'status': after.get('status')})
        return await self.query.get_match(match_id)

    async def update_admin_match_score(self, match_id: int, payload: MatchScoreUpdateRequest, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            self._validate_score_payload(payload, best_of_sets=int(match.best_of_sets or 3))
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
        await self.workflows.process_match_event(match_id, event_type=payload.event_type, set_number=payload.set_number, payload_json=payload.payload_json or {})
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
            target_status = self._resolve_finalize_status(str(match.status or 'scheduled'))
            if target_status == 'finished' and not sets:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Нельзя завершить матч без данных по сетам.')
            winner_id = self._decide_winner(match, sets, target_status=target_status)
            if winner_id is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Не удалось определить победителя матча.')
            if match.status == target_status and match.winner_id == winner_id and match.actual_end_at is not None:
                return self._action_result(
                    entity_type='match',
                    action='finalize',
                    entity_id=match_id,
                    message='Матч уже завершен.',
                    status='ok',
                    details={'winner_id': winner_id, 'idempotent': True},
                )
            updated = await self.matches.update(session, match, {'status': target_status, 'winner_id': winner_id, 'actual_end_at': datetime.now(tz=UTC)})
            after = self._entity_dict(updated)
        await self._log_audit(action='match.finalize', entity_type='match', entity_id=match_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('matches:', 'players:', 'tournaments:', 'live:', 'rankings:')
        await self._broadcast_match_update(match_id, 'match_finished', {'winner_id': winner_id})
        job = await self.jobs.enqueue(job_type='finalize_match_postprocess', payload={'match_id': match_id, 'actor_id': actor_id})
        await self.jobs.process_due_jobs()
        current_job = next(item for item in self.jobs.list_jobs() if int(item['id']) == int(job['id']))
        return self._action_result(
            entity_type='match',
            action='finalize',
            entity_id=match_id,
            message='Match finalized and post-processing queued',
            job_id=int(job['id']),
            status=str(current_job.get('status') or 'pending'),
            details={'winner_id': winner_id, **(current_job.get('result') or {})},
        )

    async def reopen_admin_match(self, match_id: int, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            before = self._entity_dict(match)
            current_status = self._normalize_match_status(str(match.status or 'scheduled'))
            if current_status == 'scheduled' and match.winner_id is None and match.actual_end_at is None:
                return self._action_result(entity_type='match', action='reopen', entity_id=match_id, message='Матч уже открыт для редактирования.', details={'status': 'scheduled', 'idempotent': True})
            if current_status not in self.TERMINAL_MATCH_STATUSES:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Открыть заново можно только завершенный, отмененный или перенесенный матч.')
            updated = await self.matches.update(session, match, {'status': 'scheduled', 'winner_id': None, 'actual_end_at': None, 'retire_reason': None, 'walkover_reason': None})
            after = self._entity_dict(updated)
        if current_status in self.COMPLETED_MATCH_STATUSES:
            await self.workflows.rollback_finalized_match(match_id)
        await self._log_audit(action='match.reopen', entity_type='match', entity_id=match_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('matches:', 'players:', 'tournaments:', 'live:')
        await self._broadcast_match_update(match_id, 'match_status_changed', {'status': 'scheduled'})
        return self._action_result(entity_type='match', action='reopen', entity_id=match_id, message='Match reopened', details={'status': 'scheduled'})

    async def list_admin_news(self, *, search: str | None = None, status: str | None = None):
        async with db_session_manager.session() as session:
            items, _total = await self.news.list(session, page=1, per_page=100, search=search, status=status)
            categories = {category.id: category for category in await self.news.list_categories(session)}
            data = [self.query._news_summary(item, categories.get(item.category_id), await self.query._news_tags(session, item.id)) for item in items]
        return SuccessResponse(data=data)

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
        return self._action_result(entity_type='news', action='delete', entity_id=news_id, message='News deleted')

    async def update_admin_news_status(self, news_id: int, payload: NewsStatusRequest, actor_id: int | None = None):
        async with db_session_manager.session() as session:
            article = await self.news.get(session, news_id)
            if article is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='News not found')
            before = self._entity_dict(article)
            next_status = self._ensure_news_transition(str(article.status or 'draft'), payload.status)
            publish_at = datetime.fromisoformat(payload.publish_at) if payload.publish_at else (datetime.now(tz=UTC) if next_status == 'published' else article.published_at)
            updated = await self.news.update(session, article, {'status': next_status, 'published_at': publish_at})
            after = self._entity_dict(updated)
        await self._log_audit(action='news.update_status', entity_type='news', entity_id=news_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('news:', 'search:', 'players:', 'tournaments:')
        if before.get('status') != after.get('status') and after.get('status') == 'published':
            await self.workflows.process_published_news(news_id)
        return await self.query.get_news_article(updated.slug)

    async def publish_admin_news(self, news_id: int, actor_id: int | None = None):
        await self.update_admin_news_status(news_id, NewsStatusRequest(status='published', publish_at=None), actor_id=actor_id)
        return self._action_result(entity_type='news', action='publish', entity_id=news_id, message='News published', details={'status': 'published'})

    async def schedule_admin_news(self, news_id: int, payload: NewsStatusRequest, actor_id: int | None = None):
        if not payload.publish_at:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='publish_at is required')
        await self.update_admin_news_status(news_id, NewsStatusRequest(status='scheduled', publish_at=payload.publish_at), actor_id=actor_id)
        scheduled_for = datetime.fromisoformat(payload.publish_at)
        job = await self.jobs.enqueue(job_type='publish_scheduled_news', payload={'news_id': news_id}, run_at=scheduled_for)
        return self._action_result(
            entity_type='news',
            action='schedule',
            entity_id=news_id,
            message=f'News scheduled for {payload.publish_at}',
            job_id=int(job['id']),
            status='scheduled',
            scheduled_at=scheduled_for,
            details={'status': 'scheduled'},
        )

    async def upload_admin_news_cover(self, news_id: int, payload: dict[str, Any], actor_id: int | None = None):
        cover_image_url = str(payload.get('cover_image_url') or '').strip()
        if not cover_image_url:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='cover_image_url is required')
        async with db_session_manager.session() as session:
            article = await self.news.get(session, news_id)
            if article is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='News not found')
            before = self._entity_dict(article)
            updated = await self.news.update(session, article, {'cover_image_url': cover_image_url})
            after = self._entity_dict(updated)
        await self._log_audit(action='news.cover.update', entity_type='news', entity_id=news_id, before_json=before, after_json=after, user_id=actor_id)
        self._invalidate_cache('news:', 'search:', 'players:', 'tournaments:')
        return self._action_result(entity_type='news', action='cover.update', entity_id=news_id, message='News cover updated', details={'cover_image_url': cover_image_url})

    async def attach_admin_news_tags(self, news_id: int, payload: dict[str, Any] | None = None, actor_id: int | None = None):
        payload = payload or {}
        raw_tag_ids = payload.get('tag_ids')
        async with db_session_manager.session() as session:
            article = await self.news.get(session, news_id)
            if article is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='News not found')
            mapping = self._news_tag_mapping()
            if raw_tag_ids is None:
                tag_ids = [int(item) for item in mapping.get(str(news_id), [])]
            elif isinstance(raw_tag_ids, list):
                tag_ids = [int(item) for item in raw_tag_ids]
            else:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='tag_ids is required')
            tags = await self.news.get_tags_by_ids(session, tag_ids)
            if raw_tag_ids is not None and len(tags) != len(set(tag_ids)):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Some tags were not found')
        if raw_tag_ids is None:
            return SuccessResponse(data=[TagItem(id=item.id, slug=item.slug, name=item.name) for item in tags])

        before = list(mapping.get(str(news_id), []))
        mapping[str(news_id)] = sorted({item.id for item in tags})
        self._save_news_tag_mapping(mapping)
        await self._log_audit(action='news.tags.update', entity_type='news', entity_id=news_id, before_json={'tag_ids': before}, after_json={'tag_ids': mapping[str(news_id)]}, user_id=actor_id)
        self._invalidate_cache('news:', 'search:', 'players:', 'tournaments:')
        return SuccessResponse(data=[TagItem(id=item.id, slug=item.slug, name=item.name) for item in tags])
