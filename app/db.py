from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


async def reset_engine(database_url: str | None = None) -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    if database_url is not None:
        import os

        os.environ["DATABASE_URL"] = database_url
        get_settings.cache_clear()
    get_engine()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session


async def check_database_connection() -> bool:
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
