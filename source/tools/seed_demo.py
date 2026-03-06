import asyncio

from sqlalchemy import select

from source.config.settings import settings
from source.db.bootstrap import seed_demo_data
from source.db.models import Player
from source.db.session import db_session_manager


async def main() -> None:
    original_flag = settings.db.seed_demo_data
    settings.db.seed_demo_data = True
    try:
        async with db_session_manager.session() as session:
            exists = await session.scalar(select(Player.id).limit(1))
            if exists is None:
                await seed_demo_data(session, force=True)
                print('Демо-данные успешно загружены.')
            else:
                print('Демо-данные уже существуют. Повторная загрузка не требуется.')
    finally:
        settings.db.seed_demo_data = original_flag
        await db_session_manager.dispose()


if __name__ == '__main__':
    asyncio.run(main())
