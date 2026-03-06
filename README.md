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

Default local runtime is PostgreSQL-first. Tests also try PostgreSQL first by creating an isolated temporary database; if PostgreSQL is unavailable, they fall back to an isolated SQLite file to keep local runs hermetic.

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

## Docker dev mode

Dev mode mounts the project into containers, enables `uvicorn --reload`, and auto-refreshes the browser when Python, HTML, CSS, or JS files change.

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

In this mode:
- code changes do not require manual image rebuilds
- backend reloads automatically
- templates and static assets trigger automatic browser refresh
- worker process restarts automatically when Python code changes
- demo data seeding is enabled for convenience

Use `--build` only on the first launch or after dependency changes in `pyproject.toml` or the Docker image.

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
