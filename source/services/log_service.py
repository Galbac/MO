from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from source.config.settings import settings


class LogService:
    allowed_categories = {"access", "application", "worker", "integration"}

    def __init__(self) -> None:
        self.base_dir = Path(settings.logging.dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, category: str) -> Path:
        normalized = category if category in self.allowed_categories else "application"
        return self.base_dir / f"{normalized}.jsonl"

    def write(self, category: str, *, level: str = "info", message: str, context: dict[str, Any] | None = None) -> None:
        payload = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "category": category if category in self.allowed_categories else "application",
            "level": level,
            "message": message,
            "context": context or {},
        }
        target = self._path(category)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def read(self, category: str, *, level: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        path = self._path(category)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if level and str(item.get("level")) != level:
                continue
            rows.append(item)
        return rows[-max(1, min(limit, 500)):]

    def categories(self) -> list[str]:
        return sorted(self.allowed_categories)

    def summary(self, *, category: str | None = None, level: str | None = None, limit: int = 500) -> dict[str, Any]:
        categories = [category] if category else self.categories()
        rows: list[dict[str, Any]] = []
        for item in categories:
            rows.extend(self.read(item, level=level, limit=limit))
        by_level: dict[str, int] = {}
        latest_at = None
        for row in rows:
            level_value = str(row.get("level") or "info")
            by_level[level_value] = by_level.get(level_value, 0) + 1
            timestamp = row.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    parsed = datetime.fromisoformat(timestamp)
                except ValueError:
                    parsed = None
                if parsed is not None and (latest_at is None or parsed > latest_at):
                    latest_at = parsed
        return {
            "total": len(rows),
            "categories": categories,
            "by_level": by_level,
            "latest_at": latest_at,
        }
