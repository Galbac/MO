# Tennis Portal

FastAPI-based tennis portal aligned to the `mediann-vpn` project structure.

## Current state

Implemented:
- public/admin API v1
- DB-backed services and repositories
- auth, RBAC, audit logging
- public/admin Jinja frontend with fetch integration
- live HTTP + WebSocket updates
- cache, jobs, workflow processing
- Alembic migration scaffold
- Docker, Nginx, PostgreSQL/Redis compose wiring
- automated API/runtime tests

## Local dev

```bash
poetry install
poetry run uvicorn source.main:create_app --factory --reload
```

Default local runtime is PostgreSQL-first. Tests explicitly override the DB engine to an isolated SQLite file per run.

## Docker stack

```bash
docker compose up --build
```

Services:
- `postgres` on `5432`
- `redis` on `6379`
- `migrate` runs `alembic upgrade head`
- `api` runs FastAPI on internal `8000`
- `nginx` exposes the app on `http://localhost:8080`

Compose runs in PostgreSQL-first mode with Redis enabled.

## Migrations

```bash
alembic upgrade head
```

`alembic/env.py` is configured for async SQLAlchemy URLs, including `postgresql+asyncpg`.

## Testing

```bash
./.venv/bin/pytest -q
```

Current suite covers auth, RBAC, admin CRUD, cache invalidation, workflows, live WebSocket flow, and runtime infrastructure.
