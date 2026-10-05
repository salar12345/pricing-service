import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

EVENT_STREAM = "asanbar:events"
EVENT_TYPE = "price_snapshot.created"


@dataclass(frozen=True)
class PriceSnapshotCreatedEvent:
    event_id: UUID
    shipment_id: str
    price_snapshot_id: UUID
    quote_id: UUID
    gross_amount: int
    commission_amount: int
    driver_net_amount: int
    occurred_at: datetime
    correlation_id: str | None


class EventPublisher(Protocol):
    async def publish_price_snapshot_created(self, event: PriceSnapshotCreatedEvent) -> None: ...


def build_event_payload(event: PriceSnapshotCreatedEvent) -> dict:
    return {
        "event_id": str(event.event_id),
        "event_type": EVENT_TYPE,
        "occurred_at": event.occurred_at.isoformat(),
        "correlation_id": event.correlation_id,
        "data": {
            "shipment_id": event.shipment_id,
            "price_snapshot_id": str(event.price_snapshot_id),
            "quote_id": str(event.quote_id),
            "gross_amount": event.gross_amount,
            "commission_amount": event.commission_amount,
            "driver_net_amount": event.driver_net_amount,
            "currency": "IRR",
        },
    }


class NoOpEventPublisher:
    async def publish_price_snapshot_created(self, event: PriceSnapshotCreatedEvent) -> None:
        return None


class RedisEventPublisher:
    def __init__(self, redis: Redis, stream: str = EVENT_STREAM) -> None:
        self._redis = redis
        self._stream = stream

    async def publish_price_snapshot_created(self, event: PriceSnapshotCreatedEvent) -> None:
        payload = build_event_payload(event)
        await self._redis.xadd(self._stream, {"payload": json.dumps(payload)})
