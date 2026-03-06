from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel


class ProviderRankingRow(BaseModel):
    ranking_type: str
    ranking_date: str
    position: int
    player_name: str
    country_code: str
    points: int
    movement: int | None = None


class ProviderLiveEvent(BaseModel):
    provider: str
    event_type: str
    match_slug: str
    tournament_name: str
    player1_name: str
    player2_name: str
    status: str
    score_summary: str | None = None
    occurred_at: datetime
    payload: dict[str, Any]


class ProviderPayloadMapper:
    def parse_rankings(self, provider: str, payload: dict[str, Any]) -> list[ProviderRankingRow]:
        provider_name = provider.strip().lower()
        if provider_name not in {'rankings-provider', 'rankings_provider', 'rankings'}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Unsupported rankings provider')

        ranking_type = str(payload.get('ranking_type') or 'atp').strip().lower()
        ranking_date = str(payload.get('ranking_date') or '').strip()
        entries = payload.get('entries') or payload.get('rows') or []
        if not ranking_date or not isinstance(entries, list) or not entries:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid rankings payload')

        normalized: list[ProviderRankingRow] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid rankings entry')
            position = entry.get('position', entry.get('rank'))
            player_name = entry.get('player_name', entry.get('player'))
            country_code = entry.get('country_code', entry.get('country', 'UNK'))
            points = entry.get('points')
            if position in (None, '') or not player_name or points in (None, ''):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Incomplete rankings entry')
            movement = entry.get('movement')
            normalized.append(
                ProviderRankingRow(
                    ranking_type=ranking_type,
                    ranking_date=ranking_date,
                    position=int(position),
                    player_name=str(player_name).strip(),
                    country_code=str(country_code).strip().upper() or 'UNK',
                    points=int(points),
                    movement=int(movement) if movement not in (None, '') else None,
                )
            )
        normalized.sort(key=lambda item: item.position)
        return normalized

    def parse_live_events(self, provider: str, payload: dict[str, Any]) -> list[ProviderLiveEvent]:
        provider_name = provider.strip().lower()
        if provider_name not in {'live-provider', 'live_score_provider', 'live-score-provider', 'live'}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Unsupported live provider')

        raw_items = payload.get('events') or [payload]
        if not isinstance(raw_items, list) or not raw_items:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid live payload')

        normalized: list[ProviderLiveEvent] = []
        for item in raw_items:
            if not isinstance(item, dict):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid live event')
            match_payload = item.get('match') or {}
            tournament_name = str(match_payload.get('tournament_name') or item.get('tournament_name') or '').strip()
            slug = str(match_payload.get('slug') or item.get('match_slug') or '').strip()
            status_value = str(match_payload.get('status') or item.get('status') or 'live').strip()
            event_type = str(item.get('event_type') or item.get('type') or '').strip()
            players = item.get('players') or []
            player1_name = ''
            player2_name = ''
            if isinstance(players, list) and len(players) >= 2:
                player1_name = str(players[0].get('name') or '').strip()
                player2_name = str(players[1].get('name') or '').strip()
            else:
                player1_name = str(item.get('player1_name') or '').strip()
                player2_name = str(item.get('player2_name') or '').strip()
            timestamp = item.get('occurred_at') or item.get('timestamp')
            if not slug or not tournament_name or not player1_name or not player2_name or not event_type:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Incomplete live event')
            occurred_at = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00')) if timestamp else datetime.now(tz=UTC)
            normalized.append(
                ProviderLiveEvent(
                    provider=provider_name,
                    event_type=event_type,
                    match_slug=slug,
                    tournament_name=tournament_name,
                    player1_name=player1_name,
                    player2_name=player2_name,
                    status=status_value,
                    score_summary=(match_payload.get('score_summary') or item.get('score_summary')),
                    occurred_at=occurred_at,
                    payload=item,
                )
            )
        normalized.sort(key=lambda event: event.occurred_at)
        return normalized
