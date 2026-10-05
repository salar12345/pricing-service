import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.api.deps import reset_event_publisher, set_event_publisher
from app.events.publisher import PriceSnapshotCreatedEvent
from app.models.snapshot import PriceSnapshot

QUOTE_URL = "/api/v1/pricing/shipments/{shipment_id}/quote"
CONFIRM_URL = "/api/v1/pricing/shipments/{shipment_id}/confirm-snapshot"
SNAPSHOT_URL = "/api/v1/pricing/shipments/{shipment_id}/snapshot"

SPEC_BODY = {
    "inputs": {
        "distance_km": 450,
        "stop_count": 2,
        "cargo_type": "general",
        "vehicle_type": "trailer",
    },
    "force_recalculate": False,
}


class CountingEventPublisher:
    def __init__(self) -> None:
        self.count = 0
        self.events: list[PriceSnapshotCreatedEvent] = []

    async def publish_price_snapshot_created(self, event: PriceSnapshotCreatedEvent) -> None:
        self.count += 1
        self.events.append(event)


@pytest.fixture
def counting_publisher() -> CountingEventPublisher:
    publisher = CountingEventPublisher()
    set_event_publisher(publisher)
    yield publisher
    reset_event_publisher()


async def _create_quote(client: AsyncClient, shipment_id: str) -> None:
    response = await client.post(QUOTE_URL.format(shipment_id=shipment_id), json=SPEC_BODY)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_confirm_snapshot_success(
    client: AsyncClient, counting_publisher: CountingEventPublisher
) -> None:
    shipment_id = "shp-confirm-1"
    await _create_quote(client, shipment_id)

    response = await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-001"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["shipment_id"] == shipment_id
    assert data["gross_amount"] == 5_900_000
    assert data["currency"] == "IRR"
    assert counting_publisher.count == 1


@pytest.mark.asyncio
async def test_confirm_idempotent_replay(
    client: AsyncClient, counting_publisher: CountingEventPublisher
) -> None:
    shipment_id = "shp-idempotent"
    await _create_quote(client, shipment_id)

    first = await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-replay"},
    )
    second = await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-replay"},
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["snapshot_id"] == second.json()["snapshot_id"]
    assert counting_publisher.count == 1


@pytest.mark.asyncio
async def test_confirm_twice_different_key_returns_409(client: AsyncClient) -> None:
    shipment_id = "shp-double-confirm"
    await _create_quote(client, shipment_id)

    first = await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-a"},
    )
    second = await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-b"},
    )
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SNAPSHOT_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_confirm_no_quote_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        CONFIRM_URL.format(shipment_id="shp-no-quote"),
        headers={"Idempotency-Key": "idem-no-quote"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUOTE_NOT_FOUND"


@pytest.mark.asyncio
async def test_idempotency_conflict(client: AsyncClient) -> None:
    await _create_quote(client, "shp-conflict-a")
    await _create_quote(client, "shp-conflict-b")

    first = await client.post(
        CONFIRM_URL.format(shipment_id="shp-conflict-a"),
        headers={"Idempotency-Key": "shared-key"},
    )
    second = await client.post(
        CONFIRM_URL.format(shipment_id="shp-conflict-b"),
        headers={"Idempotency-Key": "shared-key"},
    )
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_get_snapshot(client: AsyncClient) -> None:
    shipment_id = "shp-get-snapshot"
    await _create_quote(client, shipment_id)
    confirmed = await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-get"},
    )
    assert confirmed.status_code == 201

    response = await client.get(SNAPSHOT_URL.format(shipment_id=shipment_id))
    assert response.status_code == 200
    assert response.json()["snapshot_id"] == confirmed.json()["snapshot_id"]


@pytest.mark.asyncio
async def test_get_snapshot_not_found(client: AsyncClient) -> None:
    response = await client.get(SNAPSHOT_URL.format(shipment_id="shp-no-snapshot"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SNAPSHOT_NOT_FOUND"


@pytest.mark.asyncio
async def test_idempotent_replay_creates_one_snapshot_row(
    client: AsyncClient, database_urls: dict[str, str]
) -> None:
    from app.db import get_session_factory, reset_engine

    shipment_id = "shp-one-row"
    await _create_quote(client, shipment_id)

    await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-one-row"},
    )
    await client.post(
        CONFIRM_URL.format(shipment_id=shipment_id),
        headers={"Idempotency-Key": "idem-one-row"},
    )

    await reset_engine(database_urls["async"])
    async with get_session_factory()() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(PriceSnapshot)
            .where(PriceSnapshot.shipment_id == shipment_id)
        )
    assert count == 1
