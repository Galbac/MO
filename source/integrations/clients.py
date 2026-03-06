from __future__ import annotations

import asyncio
from typing import Any

import httpx

from source.integrations.provider_contracts import ProviderLiveEvent, ProviderPayloadMapper, ProviderRankingRow


class IntegrationSyncError(RuntimeError):
    pass


class BaseProviderClient:
    def __init__(self, provider: str, *, timeout_seconds: float = 5.0, max_attempts: int = 3, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.transport = transport
        self.mapper = ProviderPayloadMapper()

    async def _request_json(self, endpoint: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = await client.get(endpoint, headers=headers)
                    if response.status_code >= 500:
                        raise IntegrationSyncError(f'Provider responded with server error {response.status_code}')
                    if response.status_code >= 400:
                        raise IntegrationSyncError(f'Provider responded with client error {response.status_code}')
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise IntegrationSyncError('Provider returned non-object JSON payload')
                    return payload
                except (httpx.RequestError, httpx.TimeoutException, ValueError, IntegrationSyncError) as exc:
                    last_error = exc
                    if attempt >= self.max_attempts:
                        break
                    await asyncio.sleep(min(0.05 * attempt, 0.15))
        raise IntegrationSyncError(str(last_error or 'Provider request failed'))


class LiveScoreProviderClient(BaseProviderClient):
    async def fetch_events(self, endpoint: str, headers: dict[str, str] | None = None) -> list[ProviderLiveEvent]:
        payload = await self._request_json(endpoint, headers=headers)
        return self.mapper.parse_live_events(self.provider, payload)


class RankingsProviderClient(BaseProviderClient):
    async def fetch_rankings(self, endpoint: str, headers: dict[str, str] | None = None) -> list[ProviderRankingRow]:
        payload = await self._request_json(endpoint, headers=headers)
        return self.mapper.parse_rankings(self.provider, payload)
