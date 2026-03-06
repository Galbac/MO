from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from fastapi import HTTPException, status

from source.config.settings import settings


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode())


class TokenCodec:
    def __init__(self, secret: str) -> None:
        self.secret = secret.encode()

    def encode(self, payload: dict[str, Any]) -> str:
        body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
        signature = hmac.new(self.secret, body.encode(), hashlib.sha256).digest()
        return f"{body}.{_b64encode(signature)}"

    def decode(self, token: str) -> dict[str, Any]:
        try:
            body, signature = token.split('.', 1)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token') from exc
        expected = _b64encode(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token signature')
        payload = json.loads(_b64decode(body))
        exp = payload.get('exp')
        if exp is not None and int(exp) < int(time.time()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token expired')
        return payload

    def issue_access_token(self, user_id: int) -> str:
        now = int(time.time())
        return self.encode({'sub': user_id, 'typ': 'access', 'iat': now, 'exp': now + settings.auth.access_token_ttl_minutes * 60})

    def issue_refresh_token(self, user_id: int) -> tuple[str, dict[str, Any]]:
        now = int(time.time())
        payload = {'sub': user_id, 'typ': 'refresh', 'iat': now, 'exp': now + settings.auth.refresh_token_ttl_minutes * 60, 'jti': uuid.uuid4().hex}
        return self.encode(payload), payload


token_codec = TokenCodec(settings.auth.secret_key)
