from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from source.db.models import User


class UserRepository:
    async def list(self, session: AsyncSession) -> list[User]:
        stmt = select(User).order_by(User.id.asc())
        return list((await session.scalars(stmt)).all())

    async def get(self, session: AsyncSession, user_id: int) -> User | None:
        return await session.get(User, user_id)

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return await session.scalar(stmt)

    async def get_by_username(self, session: AsyncSession, username: str) -> User | None:
        stmt = select(User).where(func.lower(User.username) == username.lower())
        return await session.scalar(stmt)

    async def get_by_login(self, session: AsyncSession, email_or_username: str) -> User | None:
        value = email_or_username.lower()
        stmt = select(User).where(or_(func.lower(User.email) == value, func.lower(User.username) == value))
        return await session.scalar(stmt)

    async def create(self, session: AsyncSession, payload: dict) -> User:
        user = User(**payload)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def update(self, session: AsyncSession, user: User, payload: dict) -> User:
        for key, value in payload.items():
            setattr(user, key, value)
        await session.commit()
        await session.refresh(user)
        return user
