from pathlib import Path

import yaml

from source.config.settings import settings


def test_docker_compose_has_postgres_redis_migrate_api_worker_nginx() -> None:
    payload = yaml.safe_load(Path('docker-compose.yml').read_text())
    services = payload['services']

    assert {'postgres', 'redis', 'migrate', 'api', 'worker', 'nginx'}.issubset(services)
    assert services['api']['environment']['FASTAPI_CFG__DB__URL'].startswith('postgresql+asyncpg://')
    assert services['api']['environment']['FASTAPI_CFG__REDIS__ENABLED'] == 'true'
    assert services['migrate']['command'] == 'alembic upgrade head'
    assert services['worker']['command'] == 'python -m source.tasks.worker'
    assert services['nginx']['ports'] == ['8080:80']



def test_settings_default_db_url_is_postgres_first() -> None:
    assert settings.db.url.startswith('postgresql+asyncpg://')
