import json

import fakeredis.aioredis
import pytest
from httpx import AsyncClient

from app.api.deps import reset_event_publisher, set_event_publisher
from app.events.publisher import EVENT_STREAM, RedisEventPublisher

QUOTE_URL = "/api/v1/pricing/shipments/{shipment_id}/quote"
CONFIRM_URL = "/api/v1/pricing/shipments/{shipment_id}/confirm-snapshot"

SPEC_BODY = {
    "inputs": {
        "distance_km": 450,
        "stop_count": 2,
        "cargo_type": "general",
        "vehicle_type": "trailer",
    },
    "force_recalculate": False,
}


@pytest.fixture
async def fake_redis_publisher():
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    publisher = RedisEventPublisher(fake_redis)
    set_event_publisher(publisher)
    yield fake_redis
    await fake_redis.aclose()
    reset_event_publisher()


async def _create_quote(client: AsyncClient, shipment_id: str) -> None:
    response = await client.post(QUOTE_URL.format(shipment_id=shipment_id), json=SPEC_BODY)
    assert response.status_code == 201


async def _read_stream_payloads(redis: fakeredis.aioredis.FakeRedis) -> list[dict]:
    entries = await redis.xrange(EVENT_STREAM, min="-", max="+")
    return [json.loads(fields["payload"]) for _entry_id, fields in entries]


@pytest.mark.asyncio
async def test_first_confirm_publishes_one_redis_event(
    client: AsyncClient, fake_redis_publisher: fakeredis.aioredis.FakeRedis
) -> None:
    shipment_id = "shp-redis-1"
    await _create_quote(client, shipment_id)

    response = await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-redis-1", "X-Correlation-Id": "corr-1"},
    )
    assert response.status_code == 201
    snapshot = response.json()

    assert await fake_redis_publisher.xlen(EVENT_STREAM) == 1
    payloads = await _read_stream_payloads(fake_redis_publisher)
    event = payloads[0]

    assert event["event_type"] == "price_snapshot.created"
    assert event["correlation_id"] == "corr-1"
    assert event["data"]["shipment_id"] == shipment_id
    assert event["data"]["price_snapshot_id"] == snapshot["snapshot_id"]
    assert event["data"]["gross_amount"] == 5_900_000
    assert event["data"]["commission_amount"] == 590_000
    assert event["data"]["driver_net_amount"] == 5_310_000
    assert event["data"]["currency"] == "IRR"


@pytest.mark.asyncio
async def test_idempotent_replay_publishes_no_second_event(
    client: AsyncClient, fake_redis_publisher: fakeredis.aioredis.FakeRedis
) -> None:
    shipment_id = "shp-redis-replay"
    await _create_quote(client, shipment_id)

    first = await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-redis-replay"},
    )
    second = await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-redis-replay"},
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert await fake_redis_publisher.xlen(EVENT_STREAM) == 1


@pytest.mark.asyncio
async def test_event_payload_has_required_fields(
    client: AsyncClient, fake_redis_publisher: fakeredis.aioredis.FakeRedis
) -> None:
    shipment_id = "shp-redis-fields"
    await _create_quote(client, shipment_id)

    await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-redis-fields"},
    )

    event = (await _read_stream_payloads(fake_redis_publisher))[0]
    assert "event_id" in event
    assert "occurred_at" in event
    assert set(event["data"]) == {
        "shipment_id",
        "price_snapshot_id",
        "quote_id",
        "gross_amount",
        "commission_amount",
        "driver_net_amount",
        "currency",
    }
