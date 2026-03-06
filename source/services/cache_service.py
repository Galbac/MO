from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from pydantic import TypeAdapter

from source.config.settings import settings
from source.services.runtime_state_store import RuntimeStateStore


class CacheService:
    def __init__(self) -> None:
        self.store = RuntimeStateStore()

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

        adapter = TypeAdapter(schema)
        entry = self.store.get_cache_entry(key)
        if entry is not None:
            return adapter.validate_python(entry.get('payload'))

        value = await loader()
        self.store.set_cache_entry(key, {
            'expires_at': time.time() + float(ttl_seconds or settings.cache.default_ttl_seconds),
            'payload': adapter.dump_python(value, mode='json'),
        })
        return value

    def invalidate_prefixes(self, *prefixes: str) -> None:
        if not settings.cache.enabled:
            return
        self.store.invalidate_cache_prefixes(*prefixes)

    def clear(self) -> None:
        self.store.clear_cache()

    def backend_name(self) -> str:
        return self.store.backend_name()
