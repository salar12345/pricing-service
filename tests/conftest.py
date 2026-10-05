import os
import subprocess
import sys
from collections.abc import AsyncGenerator, Generator

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from testcontainers.community.postgres import PostgresContainer

from app.api.deps import reset_event_publisher, set_event_publisher
from app.events.publisher import RedisEventPublisher


def _to_asyncpg_url(sync_url: str) -> str:
    return sync_url.replace("postgresql://", "postgresql+asyncpg://").replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )


def _to_psycopg2_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def database_urls(postgres_container: PostgresContainer) -> dict[str, str]:
    sync_url = postgres_container.get_connection_url()
    async_url = _to_asyncpg_url(sync_url)
    return {"sync": _to_psycopg2_url(sync_url), "async": async_url}


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(database_urls: dict[str, str]) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_urls["async"]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade failed:\n{result.stderr}")


@pytest.fixture(scope="session", autouse=True)
def configure_test_database(database_urls: dict[str, str]) -> None:
    os.environ["DATABASE_URL"] = database_urls["async"]


@pytest_asyncio.fixture
async def client(database_urls: dict[str, str]) -> AsyncGenerator[AsyncClient, None]:
    from app.db import reset_engine
    from app.main import app

    await reset_engine(database_urls["async"])

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    set_event_publisher(RedisEventPublisher(fake_redis))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await fake_redis.aclose()
    reset_event_publisher()
