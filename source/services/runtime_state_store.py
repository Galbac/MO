from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from source.config.settings import settings


class RuntimeStateStore:
    def __init__(self) -> None:
        self.base_path = Path(settings.redis.state_fallback_path)
        self._redis_client: Redis | None = None
        self._redis_checked = False

    def _namespace_path(self, namespace: str) -> Path:
        mapped = {
            'cache': Path(settings.cache.storage_path),
            'jobs': Path(settings.jobs.storage_path),
            'auth_security': self.base_path.parent / 'auth_security.json',
            'refresh_tokens': self.base_path.parent / 'refresh_tokens.json',
            'auth_action_tokens': self.base_path.parent / 'auth_action_tokens.json',
        }
        return mapped.get(namespace, self.base_path / f'{namespace}.json')

    def _ensure_local_storage(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _read_local_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return default

    def _write_local_json(self, path: Path, payload: Any) -> None:
        self._ensure_local_storage()
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))

    def _redis_key(self, namespace: str) -> str:
        return f'{settings.redis.key_prefix}:state:{namespace}'

    def _cache_key(self, key: str) -> str:
        return f'{settings.redis.key_prefix}:cache:{key}'

    def _get_redis(self) -> Redis | None:
        if self._redis_checked:
            return self._redis_client
        self._redis_checked = True
        if not settings.redis.enabled:
            return None
        try:
            client = Redis.from_url(settings.redis.url, socket_connect_timeout=settings.redis.connect_timeout_seconds, socket_timeout=settings.redis.connect_timeout_seconds, decode_responses=True)
            client.ping()
            self._redis_client = client
        except RedisError:
            self._redis_client = None
        return self._redis_client

    def read_namespace(self, namespace: str, default: Any) -> Any:
        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                raw = redis_client.get(self._redis_key(namespace))
                if raw is None:
                    return default
                return json.loads(raw)
            except RedisError:
                pass
        return self._read_local_json(self._namespace_path(namespace), default)

    def write_namespace(self, namespace: str, payload: Any) -> None:
        redis_client = self._get_redis()
        serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        if redis_client is not None:
            try:
                redis_client.set(self._redis_key(namespace), serialized)
            except RedisError:
                self._write_local_json(self._namespace_path(namespace), payload)
                return
        else:
            self._write_local_json(self._namespace_path(namespace), payload)

    def delete_namespace(self, namespace: str) -> None:
        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                redis_client.delete(self._redis_key(namespace))
            except RedisError:
                pass
        path = self._namespace_path(namespace)
        if path.exists():
            path.unlink()

    def get_cache_entry(self, key: str) -> dict[str, Any] | None:
        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                raw = redis_client.get(self._cache_key(key))
                if raw is None:
                    return None
                payload = json.loads(raw)
                if float(payload.get('expires_at', 0)) <= time.time():
                    redis_client.delete(self._cache_key(key))
                    return None
                return payload
            except RedisError:
                pass
        store = self.read_namespace('cache', {})
        entry = store.get(key)
        if entry is None:
            return None
        if float(entry.get('expires_at', 0)) <= time.time():
            store.pop(key, None)
            self.write_namespace('cache', store)
            return None
        return entry

    def set_cache_entry(self, key: str, payload: dict[str, Any]) -> None:
        redis_client = self._get_redis()
        ttl_seconds = max(int(float(payload.get('expires_at', time.time())) - time.time()), 1)
        if redis_client is not None:
            try:
                redis_client.setex(self._cache_key(key), ttl_seconds, json.dumps(payload, ensure_ascii=True, sort_keys=True))
                return
            except RedisError:
                pass
        store = self.read_namespace('cache', {})
        store[key] = payload
        self.write_namespace('cache', store)

    def invalidate_cache_prefixes(self, *prefixes: str) -> None:
        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                for prefix in prefixes:
                    pattern = self._cache_key(f'{prefix}*')
                    for key in redis_client.scan_iter(match=pattern):
                        redis_client.delete(key)
            except RedisError:
                pass
        store = self.read_namespace('cache', {})
        filtered = {key: value for key, value in store.items() if not any(key.startswith(prefix) for prefix in prefixes)}
        self.write_namespace('cache', filtered)

    def clear_cache(self) -> None:
        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                for key in redis_client.scan_iter(match=self._cache_key('*')):
                    redis_client.delete(key)
            except RedisError:
                pass
        self.write_namespace('cache', {})

    def backend_name(self) -> str:
        return 'redis' if self._get_redis() is not None else 'local'
