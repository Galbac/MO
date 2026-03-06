from __future__ import annotations

from datetime import UTC, date, datetime, time as clock_time
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from source.config.settings import settings
from source.db.models import Match, NewsArticle, Tournament
from source.db.session import db_session_manager
from source.repositories import EngagementRepository, MatchRepository, NewsRepository, PlayerRepository, TournamentRepository, UserRepository
from source.services.cache_service import CacheService


class WorkflowService:
    @staticmethod
    def _surface_record(wins: int, losses: int) -> str:
        return f'{wins}-{losses}'

    @staticmethod
    def _in_quiet_hours(user, now_utc: datetime) -> bool:
        start = getattr(user, 'quiet_hours_start', None)
        end = getattr(user, 'quiet_hours_end', None)
        if not start or not end:
            return False
        try:
            user_tz = ZoneInfo(getattr(user, 'timezone', 'UTC') or 'UTC')
            local_time = now_utc.astimezone(user_tz).time()
            start_time = clock_time.fromisoformat(start)
            end_time = clock_time.fromisoformat(end)
        except Exception:
            return False
        if start_time == end_time:
            return True
        if start_time < end_time:
            return start_time <= local_time < end_time
        return local_time >= start_time or local_time < end_time

    def __init__(self) -> None:
        self.matches = MatchRepository()
        self.engagement = EngagementRepository()
        self.news = NewsRepository()
        self.players = PlayerRepository()
        self.tournaments = TournamentRepository()
        self.users = UserRepository()
        self.cache = CacheService()
        self.artifacts_dir = Path(settings.maintenance.artifacts_dir)
        self.delivery_log_path = Path(settings.notifications.delivery_log_path)

    def _artifact_path(self, filename: str) -> Path:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        return self.artifacts_dir / filename

    def _player_aggregates_path(self) -> Path:
        return self._artifact_path('player_aggregates.json')

    def _read_player_aggregates(self) -> dict[str, Any]:
        path = self._player_aggregates_path()
        if not path.exists():
            return {'generated_at': None, 'players': {}}
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            return {'generated_at': None, 'players': {}}
        payload.setdefault('players', {})
        return payload

    def _write_player_aggregates(self, payload: dict[str, Any]) -> None:
        path = self._player_aggregates_path()
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))

    def _read_delivery_log(self) -> list[dict[str, Any]]:
        if not self.delivery_log_path.exists():
            return []
        return json.loads(self.delivery_log_path.read_text())

    def _write_delivery_log(self, items: list[dict[str, Any]]) -> None:
        self.delivery_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.delivery_log_path.write_text(json.dumps(items, ensure_ascii=True, indent=2, sort_keys=True))

    def _record_delivery(self, *, user_id: int, channel: str, notification_type: str, title: str, entity_type: str, entity_id: int, status: str, reason: str | None = None) -> None:
        items = self._read_delivery_log()
        items.append({
            'user_id': user_id,
            'channel': channel,
            'notification_type': notification_type,
            'title': title,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'status': status,
            'reason': reason,
            'created_at': datetime.now(tz=UTC).isoformat(),
        })
        self._write_delivery_log(items)

    async def _rebuild_player_aggregates(self, session, player_ids: set[int]) -> None:
        if not player_ids:
            return
        aggregates = self._read_player_aggregates()
        generated_at = datetime.now(tz=UTC).isoformat()
        for player_id in sorted(player_ids):
            player = await self.players.get(session, player_id)
            if player is None:
                continue
            matches = await self.players.get_matches(session, player_id)
            tournament_ids = {item.tournament_id for item in matches}
            tournaments = {
                tournament_id: await self.tournaments.get(session, tournament_id)
                for tournament_id in sorted(tournament_ids)
            }
            completed = [item for item in matches if item.winner_id is not None]
            ordered_completed = sorted(completed, key=lambda item: item.scheduled_at or datetime.min, reverse=True)
            wins = sum(1 for item in completed if item.winner_id == player_id)
            losses = sum(1 for item in completed if item.winner_id != player_id)
            surface_wins = {'hard': 0, 'clay': 0, 'grass': 0}
            surface_losses = {'hard': 0, 'clay': 0, 'grass': 0}
            titles: list[dict[str, Any]] = []

            for match in completed:
                tournament = tournaments.get(match.tournament_id)
                if tournament is None:
                    continue
                surface = (tournament.surface or '').lower()
                if surface in surface_wins:
                    if match.winner_id == player_id:
                        surface_wins[surface] += 1
                    else:
                        surface_losses[surface] += 1
                if match.winner_id == player_id and match.round_code == 'F':
                    titles.append({
                        'tournament_name': tournament.name,
                        'season_year': tournament.season_year,
                        'surface': tournament.surface,
                        'category': tournament.category,
                    })

            season = max((item.scheduled_at.year for item in matches if item.scheduled_at), default=date.today().year)
            aggregates['players'][str(player_id)] = {
                'player_id': player_id,
                'generated_at': generated_at,
                'form': ['W' if item.winner_id == player_id else 'L' for item in ordered_completed[:5]],
                'stats': {
                    'season': season,
                    'matches_played': len(completed),
                    'wins': wins,
                    'losses': losses,
                    'win_rate': round((wins / len(completed)) * 100, 1) if completed else 0.0,
                    'hard_record': self._surface_record(surface_wins['hard'], surface_losses['hard']),
                    'clay_record': self._surface_record(surface_wins['clay'], surface_losses['clay']),
                    'grass_record': self._surface_record(surface_wins['grass'], surface_losses['grass']),
                },
                'titles': titles,
            }
        aggregates['generated_at'] = generated_at
        self._write_player_aggregates(aggregates)

    async def _deliver_notification(self, session, *, user, subscription, notification_type: str, title: str, body: str, payload_json: dict[str, Any], entity_type: str, entity_id: int) -> int:
        channels = list(subscription.channels or [])
        if not channels:
            return 0
        now = datetime.now(tz=UTC)
        if self._in_quiet_hours(user, now):
            for channel in channels:
                self._record_delivery(user_id=user.id, channel=channel, notification_type=notification_type, title=title, entity_type=entity_type, entity_id=entity_id, status='suppressed', reason='quiet_hours')
            return 0
        duplicate = await self.engagement.find_duplicate_notification(
            session,
            user_id=subscription.user_id,
            type_=notification_type,
            title=title,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        if duplicate is not None:
            for channel in channels:
                self._record_delivery(user_id=user.id, channel=channel, notification_type=notification_type, title=title, entity_type=entity_type, entity_id=entity_id, status='skipped', reason='duplicate')
            return 0
        created = 0
        for channel in channels:
            if channel not in settings.notifications.active_channels:
                self._record_delivery(user_id=user.id, channel=channel, notification_type=notification_type, title=title, entity_type=entity_type, entity_id=entity_id, status='skipped', reason='inactive_channel')
                continue
            if channel == 'web':
                await self.engagement.create_notification(session, {
                    'user_id': subscription.user_id,
                    'type': notification_type,
                    'title': title,
                    'body': body,
                    'payload_json': payload_json,
                    'status': 'unread',
                    'read_at': None,
                })
                created += 1
                self._record_delivery(user_id=user.id, channel=channel, notification_type=notification_type, title=title, entity_type=entity_type, entity_id=entity_id, status='sent')
                continue
            self._record_delivery(user_id=user.id, channel=channel, notification_type=notification_type, title=title, entity_type=entity_type, entity_id=entity_id, status='queued', reason='transport_not_configured')
        return created

    async def process_finalized_match(self, match_id: int) -> None:
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            if match.status not in {'finished', 'retired', 'walkover'} or not match.winner_id:
                return
            tournament = await self.tournaments.get(session, match.tournament_id)
            if tournament is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tournament not found')
            await self.matches.upsert_h2h(
                session,
                player1_id=match.player1_id,
                player2_id=match.player2_id,
                winner_id=match.winner_id,
                surface=tournament.surface,
                match_id=match.id,
            )
            await self._rebuild_player_aggregates(session, {match.player1_id, match.player2_id})
            await self._send_match_notifications(session, match=match, tournament=tournament)
        self.cache.invalidate_prefixes('matches:', 'players:', 'tournaments:', 'live:', 'search:', 'news:')

    async def process_match_event(self, match_id: int, *, event_type: str, set_number: int | None = None, payload_json: dict[str, Any] | None = None) -> int:
        if event_type != 'set_finished':
            return 0
        payload_json = payload_json or {}
        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            tournament = await self.tournaments.get(session, match.tournament_id)
            if tournament is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tournament not found')
            player1 = await self.players.get(session, match.player1_id)
            player2 = await self.players.get(session, match.player2_id)
            player1_name = player1.full_name if player1 else 'Player 1'
            player2_name = player2.full_name if player2 else 'Player 2'
            entities = [('match', match.id), ('player', match.player1_id), ('player', match.player2_id), ('tournament', tournament.id)]
            subscriptions = await self.engagement.list_matching_subscriptions(session, entities=entities, notification_type='set_finished')
            score = str(payload_json.get('score') or match.score_summary or '')
            title = f'Set {set_number or "?"} finished: {player1_name} vs {player2_name}'
            body = f'Set {set_number or "?"} finished.' + (f' Score: {score}' if score else '')
            created = 0
            for subscription in subscriptions:
                subscription_user = await self.users.get(session, subscription.user_id)
                if subscription_user is None:
                    continue
                created += await self._deliver_notification(
                    session,
                    user=subscription_user,
                    subscription=subscription,
                    notification_type='set_finished',
                    title=title,
                    body=body,
                    payload_json={
                        'entity_type': 'match',
                        'entity_id': match.id,
                        'set_number': set_number,
                        'score': score,
                        'tournament_id': tournament.id,
                    },
                    entity_type='match',
                    entity_id=match.id,
                )
        return created

    async def process_match_status_change(self, match_id: int, status_value: str) -> int:
        notification_type = {
            'about_to_start': 'match_soon',
            'live': 'match_start',
        }.get(status_value)
        if notification_type is None:
            return 0

        async with db_session_manager.session() as session:
            match = await self.matches.get(session, match_id)
            if match is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
            tournament = await self.tournaments.get(session, match.tournament_id)
            if tournament is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tournament not found')
            player1 = await self.players.get(session, match.player1_id)
            player2 = await self.players.get(session, match.player2_id)
            player1_name = player1.full_name if player1 else 'Player 1'
            player2_name = player2.full_name if player2 else 'Player 2'
            entities = [('match', match.id), ('player', match.player1_id), ('player', match.player2_id), ('tournament', tournament.id)]
            subscriptions = await self.engagement.list_matching_subscriptions(session, entities=entities, notification_type=notification_type)
            title = f'{player1_name} vs {player2_name}'
            body = 'Match is starting soon.' if notification_type == 'match_soon' else 'Match is now live.'
            created = 0
            for subscription in subscriptions:
                subscription_user = await self.users.get(session, subscription.user_id)
                if subscription_user is None:
                    continue
                created += await self._deliver_notification(
                    session,
                    user=subscription_user,
                    subscription=subscription,
                    notification_type=notification_type,
                    title=title,
                    body=body,
                    payload_json={'entity_type': 'match', 'entity_id': match.id, 'status': status_value, 'tournament_id': tournament.id},
                    entity_type='match',
                    entity_id=match.id,
                )
        return created

    async def _send_match_notifications(self, session, *, match: Match, tournament: Tournament) -> None:
        entities = [('match', match.id), ('player', match.player1_id), ('player', match.player2_id), ('tournament', tournament.id)]
        subscriptions = await self.engagement.list_matching_subscriptions(session, entities=entities, notification_type='match_finished')
        winner_name = 'Player'
        if match.winner_id == match.player1_id:
            winner_name = 'player1'
        elif match.winner_id == match.player2_id:
            winner_name = 'player2'
        title = f'Match finished: {match.slug}'
        body = f'{title}. Winner recorded as {winner_name}.'
        for subscription in subscriptions:
            subscription_user = await self.users.get(session, subscription.user_id)
            if subscription_user is None:
                continue
            await self._deliver_notification(
                session,
                user=subscription_user,
                subscription=subscription,
                notification_type='match_finished',
                title=title,
                body=body,
                payload_json={'entity_type': 'match', 'entity_id': match.id, 'winner_id': match.winner_id, 'tournament_id': tournament.id},
                entity_type='match',
                entity_id=match.id,
            )

    async def process_ranking_updates(self, ranking_rows: list[dict[str, Any]], *, ranking_type: str, ranking_date: str) -> int:
        changed_rows = [row for row in ranking_rows if int(row.get('movement') or 0) != 0]
        if not changed_rows:
            return 0
        created = 0
        async with db_session_manager.session() as session:
            for row in changed_rows:
                player = await self.players.get(session, int(row['player_id']))
                if player is None:
                    continue
                subscriptions = await self.engagement.list_matching_subscriptions(
                    session,
                    entities=[('player', int(row['player_id']))],
                    notification_type='ranking_change',
                )
                direction = 'up' if int(row['movement']) > 0 else 'down'
                title = f'Ranking update: {player.full_name}'
                body = f'{player.full_name} moved {direction} by {abs(int(row["movement"]))} place(s) in {ranking_type.upper()} rankings.'
                for subscription in subscriptions:
                    subscription_user = await self.users.get(session, subscription.user_id)
                    if subscription_user is None:
                        continue
                    created += await self._deliver_notification(
                        session,
                        user=subscription_user,
                        subscription=subscription,
                        notification_type='ranking_change',
                        title=title,
                        body=body,
                        payload_json={'entity_type': 'player', 'entity_id': int(row['player_id']), 'ranking_type': ranking_type, 'ranking_date': ranking_date, 'movement': int(row['movement']), 'rank_position': int(row['rank_position'])},
                        entity_type='player',
                        entity_id=int(row['player_id']),
                    )
        return created

    async def publish_due_scheduled_news(self, news_id: int | None = None) -> int:
        async with db_session_manager.session() as session:
            now = datetime.now(tz=UTC)
            due_articles = await self.news.list_due_scheduled(session, now)
            if news_id is not None:
                due_articles = [item for item in due_articles if item.id == news_id]
            published = 0
            for article in due_articles:
                if article.status == 'published':
                    continue
                await self.news.update(session, article, {'status': 'published'})
                published += 1
        if published:
            self.cache.invalidate_prefixes('news:', 'search:', 'players:', 'tournaments:')
        return published

    async def generate_sitemap_snapshot(self, base_url: str | None = None) -> dict[str, object]:
        base = (base_url or '').rstrip('/')
        async with db_session_manager.session() as session:
            players, _ = await self.players.list(session, search=None, country_code=None, hand=None, status=None, rank_from=None, rank_to=None, page=1, per_page=500)
            tournaments, _ = await self.tournaments.list(session, page=1, per_page=500)
            matches, _ = await self.matches.list(session, page=1, per_page=500, status=None)
            articles, _ = await self.news.list(session, page=1, per_page=500)
        urls = ['/', '/players', '/tournaments', '/matches', '/news', '/rankings', '/live', '/h2h', '/search']
        urls.extend(f'/players/{item.slug}' for item in players if item.slug)
        urls.extend(f'/tournaments/{item.slug}' for item in tournaments if item.slug)
        urls.extend(f'/matches/{item.slug}' for item in matches if item.slug)
        urls.extend(f'/news/{item.slug}' for item in articles if item.slug)
        unique_urls = sorted(set(urls))
        payload = {
            'generated_at': datetime.now(tz=UTC).isoformat(),
            'base_url': base,
            'url_count': len(unique_urls),
            'urls': [f'{base}{url}' if base else url for url in unique_urls],
        }
        self._artifact_path('sitemap_snapshot.json').write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return payload

    async def rebuild_search_index(self) -> dict[str, object]:
        async with db_session_manager.session() as session:
            players, _ = await self.players.list(session, search=None, country_code=None, hand=None, status=None, rank_from=None, rank_to=None, page=1, per_page=500)
            tournaments, _ = await self.tournaments.list(session, page=1, per_page=500)
            matches, _ = await self.matches.list(session, page=1, per_page=500, status=None)
            articles, _ = await self.news.list(session, page=1, per_page=500)
        index = {
            'generated_at': datetime.now(tz=UTC).isoformat(),
            'players': [
                {'id': item.id, 'slug': item.slug, 'title': item.full_name, 'keywords': [item.full_name, item.country_code or '', item.country_name or '']}
                for item in players
            ],
            'tournaments': [
                {'id': item.id, 'slug': item.slug, 'title': item.name, 'keywords': [item.name, item.city or '', item.surface or '', item.category or '']}
                for item in tournaments
            ],
            'matches': [
                {'id': item.id, 'slug': item.slug, 'title': item.slug.replace('-', ' '), 'keywords': [item.slug, item.status or '', item.score_summary or '']}
                for item in matches
            ],
            'news': [
                {'id': item.id, 'slug': item.slug, 'title': item.title, 'keywords': [item.title, item.lead or '', item.subtitle or '']}
                for item in articles
            ],
        }
        index['total_documents'] = sum(len(index[key]) for key in ('players', 'tournaments', 'matches', 'news'))
        self._artifact_path('search_index.json').write_text(json.dumps(index, ensure_ascii=True, indent=2, sort_keys=True))
        return index

