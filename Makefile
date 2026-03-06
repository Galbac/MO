PYTHON ?= ./.venv/bin/python
PYTEST ?= ./.venv/bin/pytest
UVICORN ?= ./.venv/bin/uvicorn
ALEMBIC ?= ./.venv/bin/alembic

.PHONY: dev test lint format typecheck migrate-up migrate-down compose-up compose-down test-contract test-load worker jobs jobs-prune jobs-retry backup-runtime restore-runtime coverage-service

dev:
	$(UVICORN) source.main:create_app --factory --reload

test:
	$(PYTEST) -q

lint:
	./.venv/bin/ruff check source

format:
	./.venv/bin/black source

typecheck:
	./.venv/bin/mypy source

migrate-up:
	$(ALEMBIC) upgrade head

migrate-down:
	$(ALEMBIC) downgrade -1

compose-up:
	docker compose up --build

compose-down:
	docker compose down


test-contract:
	./.venv/bin/pytest -q source/tests/contract

test-load:
	./.venv/bin/pytest -q source/tests/load


worker:
	./.venv/bin/python -m source.tasks.worker

jobs:
	$(PYTHON) -m source.tasks.job_admin list

jobs-prune:
	$(PYTHON) -m source.tasks.job_admin prune

jobs-retry:
	@test -n "$(JOB_ID)" || (echo "JOB_ID is required" && exit 1)
	$(PYTHON) -m source.tasks.job_admin retry $(JOB_ID)


backup-runtime:
	$(PYTHON) -m source.tasks.runtime_backup backup

restore-runtime:
	@test -n "$(ARCHIVE)" || (echo "ARCHIVE is required" && exit 1)
	$(PYTHON) -m source.tasks.runtime_backup restore $(ARCHIVE)


coverage-service:
	$(PYTHON) -m source.tasks.service_coverage -q
