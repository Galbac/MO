import shutil
import uuid
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from source.config.settings import settings
from source.db.bootstrap import seed_demo_data
from source.db.session import db_session_manager
from source.main import create_app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def prepared_test_db() -> str:
    runtime_dir = Path('var')
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)

    original_url = db_session_manager.url

    import asyncio

    test_db_url = None
    test_db_path = None
    postgres_temp_db_name = None

    async def _try_prepare_postgres() -> str | None:
        nonlocal postgres_temp_db_name
        if not original_url.startswith('postgresql+asyncpg://'):
            return None
        url = make_url(original_url)
        maintenance_db = 'postgres'
        admin_url = url.set(database=maintenance_db)
        postgres_temp_db_name = f"tennis_portal_test_{uuid.uuid4().hex}"
        admin_engine = create_async_engine(admin_url.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT", future=True)
        try:
            async with admin_engine.connect() as connection:
                await connection.execute(text(f'CREATE DATABASE "{postgres_temp_db_name}"'))
        except Exception:
            await admin_engine.dispose()
            return None
        await admin_engine.dispose()
        return url.set(database=postgres_temp_db_name).render_as_string(hide_password=False)

    test_db_url = asyncio.run(_try_prepare_postgres())
    if test_db_url is None:
        test_db_path = Path('var') / f'test_{uuid.uuid4().hex}.db'
        test_db_path.parent.mkdir(parents=True, exist_ok=True)
        test_db_url = f'sqlite+aiosqlite:///{test_db_path.resolve()}'

    asyncio.run(db_session_manager.reconfigure(test_db_url))
    asyncio.run(db_session_manager.reset_models())

    async def _seed() -> None:
        async with db_session_manager.session() as session:
            await seed_demo_data(session, force=True)

    asyncio.run(_seed())
    try:
        yield test_db_url
    finally:
        asyncio.run(db_session_manager.dispose())
        if test_db_path and test_db_path.exists():
            test_db_path.unlink()
        if postgres_temp_db_name:
            async def _drop_postgres_db() -> None:
                url = make_url(original_url)
                admin_url = url.set(database='postgres')
                admin_engine = create_async_engine(admin_url.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT", future=True)
                try:
                    async with admin_engine.connect() as connection:
                        await connection.execute(text(f'DROP DATABASE IF EXISTS "{postgres_temp_db_name}"'))
                finally:
                    await admin_engine.dispose()

            try:
                asyncio.run(_drop_postgres_db())
            except Exception:
                pass
        asyncio.run(db_session_manager.reconfigure(original_url))


@pytest_asyncio.fixture
async def async_client(prepared_test_db: str) -> AsyncClient:
    del prepared_test_db
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await db_session_manager.dispose()


async def _login_headers(client: AsyncClient, *, email_or_username: str, password: str) -> dict[str, str]:
    response = await client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={"email_or_username": email_or_username, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_auth_headers(async_client: AsyncClient) -> dict[str, str]:
    return await _login_headers(async_client, email_or_username="demo_user", password="UserPass123")


@pytest_asyncio.fixture
async def admin_auth_headers(async_client: AsyncClient) -> dict[str, str]:
    return await _login_headers(async_client, email_or_username="admin", password="AdminPass123")


@pytest_asyncio.fixture
async def editor_auth_headers(async_client: AsyncClient) -> dict[str, str]:
    return await _login_headers(async_client, email_or_username="editor", password="EditorPass123")


@pytest_asyncio.fixture
async def operator_auth_headers(async_client: AsyncClient) -> dict[str, str]:
    return await _login_headers(async_client, email_or_username="operator", password="OperatorPass123")


@pytest_asyncio.fixture
async def user_session_client(async_client: AsyncClient) -> AsyncClient:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={"email_or_username": "demo_user", "password": "UserPass123"},
    )
    assert response.status_code == 200
    return async_client


@pytest_asyncio.fixture
async def admin_session_client(async_client: AsyncClient) -> AsyncClient:
    response = await async_client.post(
        f"{settings.api.prefix}{settings.api.v1.prefix}/auth/login",
        json={"email_or_username": "admin", "password": "AdminPass123"},
    )
    assert response.status_code == 200
    return async_client
