# Runbook

## Services
- `api`: FastAPI application
- `worker`: background job processor
- `postgres`: primary database
- `redis`: runtime state, cache and queue backend
- `nginx`: reverse proxy

## Startup
1. `make compose-up`
2. Verify `GET /api/v1/health/ready` returns `ok` dependencies.
3. Verify `/robots.txt`, `/sitemap.xml`, `/api/v1/live`, `/api/v1/rankings/current`.

## Worker checks
- Worker command: `python -m source.tasks.worker`
- Confirm scheduled jobs are processed by creating a scheduled news item or finalizing a match.

## Incident checks
- Database: confirm `postgres` healthcheck and app readiness.
- Redis: confirm `redis` healthcheck and runtime state backend.
- API rate limiting: check 429 bursts in access logs.
- Media uploads: inspect `var/media` in local mode or configured backend.

## Backup notes
- Postgres: periodic logical dumps and WAL strategy in production.
- Redis: enable AOF/RDB according to retention needs.
- Media: backup object storage or persisted media volume.


## Maintenance jobs
- `generate_sitemap`: writes `var/maintenance/sitemap_snapshot.json`.
- `rebuild_search_index`: writes `var/maintenance/search_index.json`.
- `clear_cache`: clears runtime cache prefixes or the whole cache store.

## Backup and restore
- Create local runtime backup: `make backup-runtime`.
- Restore local runtime backup: `make restore-runtime ARCHIVE=var/backups/<archive>.tar.gz`.
- Runtime backup includes local cache, jobs, auth state, maintenance artifacts and media files under `var/`.
