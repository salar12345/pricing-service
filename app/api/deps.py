from collections.abc import AsyncGenerator

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session_factory
from app.events.publisher import EventPublisher, NoOpEventPublisher, RedisEventPublisher
from app.redis_client import get_redis
from app.services.quote_service import QuoteService
from app.services.snapshot_service import SnapshotService

_event_publisher: EventPublisher | None = None


def get_event_publisher() -> EventPublisher:
    global _event_publisher
    if _event_publisher is None:
        _event_publisher = RedisEventPublisher(get_redis())
    return _event_publisher


def set_event_publisher(publisher: EventPublisher) -> None:
    global _event_publisher
    _event_publisher = publisher


def reset_event_publisher() -> None:
    global _event_publisher
    _event_publisher = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session


def get_quote_service(session: AsyncSession = Depends(get_db_session)) -> QuoteService:
    return QuoteService(session)


def get_snapshot_service(
    session: AsyncSession = Depends(get_db_session),
    publisher: EventPublisher = Depends(get_event_publisher),
) -> SnapshotService:
    return SnapshotService(session, publisher)


def get_correlation_id(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
) -> str | None:
    return x_correlation_id
