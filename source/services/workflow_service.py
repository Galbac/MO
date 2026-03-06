from __future__ import annotations

from datetime import UTC, datetime, time as clock_time
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from source.db.models import Match, NewsArticle, Tournament
from source.db.session import db_session_manager
from source.repositories import EngagementRepository, MatchRepository, NewsRepository, PlayerRepository, TournamentRepository, UserRepository
from source.services.cache_service import CacheService


class WorkflowService:
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
            await self._send_match_notifications(session, match=match, tournament=tournament)
        self.cache.invalidate_prefixes('matches:', 'players:', 'tournaments:', 'live:', 'search:', 'news:')

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
            now = datetime.now(tz=UTC)
            for subscription in subscriptions:
                subscription_user = await self.users.get(session, subscription.user_id)
                if subscription_user is None or self._in_quiet_hours(subscription_user, now):
                    continue
                duplicate = await self.engagement.find_duplicate_notification(
                    session,
                    user_id=subscription.user_id,
                    type_=notification_type,
                    title=title,
                    entity_type='match',
                    entity_id=match.id,
                )
                if duplicate is not None:
                    continue
                await self.engagement.create_notification(session, {
                    'user_id': subscription.user_id,
                    'type': notification_type,
                    'title': title,
                    'body': body,
                    'payload_json': {'entity_type': 'match', 'entity_id': match.id, 'status': status_value, 'tournament_id': tournament.id},
                    'status': 'unread',
                    'read_at': None,
                })
                created += 1
        return created

    async def _send_match_notifications(self, session, *, match: Match, tournament: Tournament) -> None:
        entities = [('match', match.id), ('player', match.player1_id), ('player', match.player2_id), ('tournament', tournament.id)]
        subscriptions = await self.engagement.list_matching_subscriptions(session, entities=entities, notification_type='match_finished')
        now = datetime.now(tz=UTC)
        winner_name = 'Player'
        if match.winner_id == match.player1_id:
            winner_name = 'player1'
        elif match.winner_id == match.player2_id:
            winner_name = 'player2'
        title = f'Match finished: {match.slug}'
        body = f'{title}. Winner recorded as {winner_name}.'
        for subscription in subscriptions:
            subscription_user = await self.users.get(session, subscription.user_id)
            if subscription_user is None or self._in_quiet_hours(subscription_user, now):
                continue
            duplicate = await self.engagement.find_duplicate_notification(
                session,
                user_id=subscription.user_id,
                type_='match_finished',
                title=title,
                entity_type='match',
                entity_id=match.id,
            )
            if duplicate is not None:
                continue
            await self.engagement.create_notification(session, {
                'user_id': subscription.user_id,
                'type': 'match_finished',
                'title': title,
                'body': body,
                'payload_json': {'entity_type': 'match', 'entity_id': match.id, 'winner_id': match.winner_id, 'tournament_id': tournament.id},
                'status': 'unread',
                'read_at': None,
            })

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
