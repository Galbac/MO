from __future__ import annotations

import time

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from source.config.settings import settings
from source.services.runtime_state_store import RuntimeStateStore


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        response.headers['Content-Security-Policy'] = "default-src 'self' https://cdn.jsdelivr.net; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; connect-src 'self' ws: wss:; font-src 'self' https://cdn.jsdelivr.net; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        return response


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.store = RuntimeStateStore()
        self.namespace = 'api_rate_limits'

    async def dispatch(self, request: Request, call_next):
        if not settings.security.api_rate_limit_enabled:
            return await call_next(request)
        if request.url.path.startswith('/static') or request.url.path.startswith('/docs'):
            return await call_next(request)
        if not request.url.path.startswith('/api/'):
            return await call_next(request)
        if request.url.path.startswith('/api/v1/health'):
            return await call_next(request)

        client_ip = request.client.host if request.client and request.client.host else 'unknown'
        now = int(time.time())
        window = settings.security.api_rate_limit_window_seconds
        limit = settings.security.api_rate_limit_requests
        state = self.store.read_namespace(self.namespace, {})
        timestamps = [int(item) for item in state.get(client_ip, []) if now - int(item) < window]
        if len(timestamps) >= limit:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    'success': False,
                    'data': None,
                    'meta': {},
                    'errors': [{'code': 'RATE_LIMITED', 'message': 'Too many requests', 'field': None}],
                },
            )
        timestamps.append(now)
        state[client_ip] = timestamps
        self.store.write_namespace(self.namespace, state)
        return await call_next(request)
