from pathlib import Path

import yaml


def test_docker_compose_has_postgres_redis_migrate_api_nginx() -> None:
    payload = yaml.safe_load(Path('docker-compose.yml').read_text())
    services = payload['services']

    assert {'postgres', 'redis', 'migrate', 'api', 'nginx'}.issubset(services)
    assert services['api']['environment']['FASTAPI_CFG__DB__URL'].startswith('postgresql+asyncpg://')
    assert services['api']['environment']['FASTAPI_CFG__REDIS__ENABLED'] == 'true'
    assert services['migrate']['command'] == 'alembic upgrade head'
    assert services['nginx']['ports'] == ['8080:80']
