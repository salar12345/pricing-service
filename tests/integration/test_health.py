import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text

from app.db import get_session_factory, reset_engine
from app.models import CommissionRule, RateCard


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_returns_ok_when_database_is_up(client: AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_database_connection_and_seed_data(database_urls: dict[str, str]) -> None:
    await reset_engine(database_urls["async"])
    async with get_session_factory()() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1

        rate_count = await session.scalar(select(func.count()).select_from(RateCard))
        commission_count = await session.scalar(select(func.count()).select_from(CommissionRule))

    assert rate_count == 3
    assert commission_count == 1


@pytest.mark.asyncio
async def test_ready_returns_503_when_database_is_down(database_urls: dict[str, str]) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    await reset_engine("postgresql+asyncpg://invalid:invalid@127.0.0.1:1/nodb")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    await reset_engine(database_urls["async"])
