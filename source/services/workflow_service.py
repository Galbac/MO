from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status

from source.db.models import Match, NewsArticle, Tournament
from source.db.session import db_session_manager
from source.repositories import EngagementRepository, MatchRepository, NewsRepository, TournamentRepository
from source.services.cache_service import CacheService


class WorkflowService:
    def __init__(self) -> None:
        self.matches = MatchRepository()
        self.engagement = EngagementRepository()
        self.news = NewsRepository()
        self.tournaments = TournamentRepository()
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
