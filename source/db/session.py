from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from source.config.settings import settings
from source.db.models import Base


class DatabaseSessionManager:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = create_async_engine(url, future=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    def _rebuild_engine(self) -> None:
        self.engine = create_async_engine(self.url, future=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def reconfigure(self, url: str) -> None:
        await self.dispose()
        self.url = url
        self._rebuild_engine()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def init_models(self) -> None:
        if not settings.db.auto_create:
            return
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def reset_models(self) -> None:
        await self.dispose()
        self._rebuild_engine()
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda conn: Base.metadata.drop_all(conn, checkfirst=True))
            await connection.run_sync(lambda conn: Base.metadata.create_all(conn, checkfirst=True))

    async def dispose(self) -> None:
        await self.engine.dispose()


db_session_manager = DatabaseSessionManager(settings.db.url)
