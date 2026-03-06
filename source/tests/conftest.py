import shutil
import uuid
from pathlib import Path

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
    test_db_path = Path('var') / f'test_{uuid.uuid4().hex}.db'
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    test_db_url = f'sqlite+aiosqlite:///{test_db_path.resolve()}'

    import asyncio

    asyncio.run(db_session_manager.reconfigure(test_db_url))
    asyncio.run(db_session_manager.reset_models())

    async def _seed() -> None:
        async with db_session_manager.session() as session:
            await seed_demo_data(session)

    asyncio.run(_seed())
    try:
        yield test_db_url
    finally:
        asyncio.run(db_session_manager.dispose())
        if test_db_path.exists():
            test_db_path.unlink()
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
