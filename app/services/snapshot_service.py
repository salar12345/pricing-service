import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import (
    IdempotencyConflictError,
    QuoteNotFoundError,
    SnapshotAlreadyExistsError,
    SnapshotNotFoundError,
)
from app.events.publisher import EventPublisher, NoOpEventPublisher, PriceSnapshotCreatedEvent
from app.models.snapshot import PriceSnapshot
from app.repositories import idempotency as idempotency_repo
from app.repositories import quote as quote_repo
from app.repositories import snapshot as snapshot_repo
from app.schemas.snapshot import SnapshotResponse


def _snapshot_to_response(snapshot: PriceSnapshot) -> SnapshotResponse:
    return SnapshotResponse(
        snapshot_id=str(snapshot.id),
        shipment_id=snapshot.shipment_id,
        quote_id=str(snapshot.quote_id),
        quote_version=snapshot.quote_version,
        gross_amount=snapshot.gross_amount,
        commission_amount=snapshot.commission_amount,
        driver_net_amount=snapshot.driver_net_amount,
        confirmed_at=snapshot.confirmed_at,
    )


class SnapshotService:
    def __init__(
        self,
        session: AsyncSession,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._session = session
        self._publisher = event_publisher or NoOpEventPublisher()

    async def confirm_snapshot(
        self,
        shipment_id: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> tuple[SnapshotResponse, bool]:
        existing_key = await idempotency_repo.get_by_key(self._session, idempotency_key)
        if existing_key is not None:
            if existing_key.shipment_id == shipment_id:
                snapshot = await snapshot_repo.get_by_id(self._session, existing_key.snapshot_id)
                if snapshot is None:
                    raise SnapshotNotFoundError(shipment_id)
                return _snapshot_to_response(snapshot), False
            raise IdempotencyConflictError(idempotency_key)

        if await snapshot_repo.get_by_shipment(self._session, shipment_id) is not None:
            raise SnapshotAlreadyExistsError(shipment_id)

        quote = await quote_repo.get_latest_quote(self._session, shipment_id)
        if quote is None:
            raise QuoteNotFoundError(shipment_id)

        snapshot = await snapshot_repo.create_snapshot(
            self._session,
            shipment_id=shipment_id,
            quote_id=quote.id,
            quote_version=quote.quote_version,
            gross_amount=quote.gross_amount,
            commission_amount=quote.commission_amount,
            driver_net_amount=quote.driver_net_amount,
        )
        await idempotency_repo.create_idempotency_key(
            self._session,
            key=idempotency_key,
            shipment_id=shipment_id,
            snapshot_id=snapshot.id,
        )
        await self._session.commit()

        await self._publisher.publish_price_snapshot_created(
            PriceSnapshotCreatedEvent(
                event_id=uuid.uuid4(),
                shipment_id=shipment_id,
                price_snapshot_id=snapshot.id,
                quote_id=quote.id,
                gross_amount=snapshot.gross_amount,
                commission_amount=snapshot.commission_amount,
                driver_net_amount=snapshot.driver_net_amount,
                occurred_at=datetime.now(UTC),
                correlation_id=correlation_id,
            )
        )
        return _snapshot_to_response(snapshot), True

    async def get_snapshot(self, shipment_id: str) -> SnapshotResponse:
        snapshot = await snapshot_repo.get_by_shipment(self._session, shipment_id)
        if snapshot is None:
            raise SnapshotNotFoundError(shipment_id)
        return _snapshot_to_response(snapshot)
