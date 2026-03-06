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
- `recalculate_player_stats`: rebuilds player aggregate artifacts.
- `recalculate_h2h`: replays H2H state for a finalized match.
- `import_rankings`: runs rankings import flow through the worker.
- `sync_live`: runs provider live sync through the worker.

## Job queue operations
- Admin queue view: `/admin/jobs`.
- Admin maintenance view: `/admin/maintenance`.
- List jobs: `make jobs`.
- Retry a failed job: `make jobs-retry JOB_ID=<id>`.
- Prune finished and failed jobs: `make jobs-prune`.
- Worker processes due jobs continuously via `make worker`.

## Backup and restore
- Create local runtime backup: `make backup-runtime`.
- Restore local runtime backup: `make restore-runtime ARCHIVE=var/backups/<archive>.tar.gz`.
- Generate service-layer coverage report: `make coverage-service`. Report is written to `var/coverage/service_coverage.json`.
- Runtime backup includes local cache, jobs, auth state, maintenance artifacts and media files under `var/`.
