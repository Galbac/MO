from pathlib import Path

import yaml

from source.config.settings import settings


def test_docker_compose_has_postgres_redis_migrate_api_worker_nginx() -> None:
    payload = yaml.safe_load(Path('docker-compose.yml').read_text())
    services = payload['services']

    assert {'postgres', 'redis', 'adminer', 'migrate', 'api', 'worker', 'nginx', 'certbot'}.issubset(services)
    assert services['api']['environment']['FASTAPI_CFG__DB__URL'] == '${DOCKER_DATABASE_URL}'
    assert services['api']['environment']['FASTAPI_CFG__REDIS__ENABLED'] == '${FASTAPI_CFG__REDIS__ENABLED}'
    assert services['migrate']['command'] == 'alembic upgrade head'
    assert services['worker']['command'] == 'python -m source.tasks.worker'
    assert services['adminer']['ports'] == ['${ADMINER_PORT}:8080']
    assert services['nginx']['ports'] == ['${HTTP_PORT}:80', '${HTTPS_PORT}:443']
    assert services['nginx']['command'] == ['/bin/sh', '/entrypoint.sh']



def test_settings_default_db_url_is_postgres_first() -> None:
    assert settings.db.url.startswith('postgresql+asyncpg://')


def test_docker_dev_compose_enables_hot_reload() -> None:
    payload = yaml.safe_load(Path('docker-compose.dev.yml').read_text())
    services = payload['services']

    assert services['api']['environment']['FASTAPI_CFG__RUN__DEV_RELOAD'] == 'true'
    assert services['api']['environment']['FASTAPI_CFG__DB__SEED_DEMO_DATA'] == 'true'
    assert '.:/app' in services['api']['volumes']
    assert services['api']['command'][0] == 'uvicorn'
    assert '--reload' in services['api']['command']
    assert '*.html' in services['api']['command']
    assert services['worker']['command'][0] == 'sh'
    assert 'watchfiles --filter python' in services['worker']['command'][2]
    assert '.:/app' in services['worker']['volumes']
