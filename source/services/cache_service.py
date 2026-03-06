from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import TypeAdapter

from source.config.settings import settings


class CacheService:
    def __init__(self) -> None:
        self.storage_path = Path(settings.cache.storage_path)

    def _ensure_storage(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_store(self) -> dict[str, dict[str, Any]]:
        if not self.storage_path.exists():
            return {}
        try:
            payload = json.loads(self.storage_path.read_text())
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def _write_store(self, payload: dict[str, dict[str, Any]]) -> None:
        self._ensure_storage()
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))

    def _prune_expired(self, store: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        now = time.time()
        return {key: value for key, value in store.items() if value.get('expires_at', 0) > now}

    async def get_or_set(
        self,
        *,
        key: str,
        schema: Any,
        loader: Callable[[], Awaitable[Any]],
        ttl_seconds: int | None = None,
    ) -> Any:
        if not settings.cache.enabled:
            return await loader()

        store = self._prune_expired(self._read_store())
        entry = store.get(key)
        adapter = TypeAdapter(schema)
        if entry is not None:
            return adapter.validate_python(entry.get('payload'))

        value = await loader()
        store[key] = {
            'expires_at': time.time() + float(ttl_seconds or settings.cache.default_ttl_seconds),
            'payload': adapter.dump_python(value, mode='json'),
        }
        self._write_store(store)
        return value

    def invalidate_prefixes(self, *prefixes: str) -> None:
        if not settings.cache.enabled:
            return
        store = self._prune_expired(self._read_store())
        filtered = {
            key: value
            for key, value in store.items()
            if not any(key.startswith(prefix) for prefix in prefixes)
        }
        self._write_store(filtered)

    def clear(self) -> None:
        self._write_store({})
