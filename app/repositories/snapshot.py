import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snapshot import PriceSnapshot


async def get_by_shipment(session: AsyncSession, shipment_id: str) -> PriceSnapshot | None:
    result = await session.execute(
        select(PriceSnapshot).where(PriceSnapshot.shipment_id == shipment_id)
    )
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, snapshot_id: uuid.UUID) -> PriceSnapshot | None:
    result = await session.execute(select(PriceSnapshot).where(PriceSnapshot.id == snapshot_id))
    return result.scalar_one_or_none()


async def create_snapshot(
    session: AsyncSession,
    *,
    shipment_id: str,
    quote_id: uuid.UUID,
    quote_version: int,
    gross_amount: int,
    commission_amount: int,
    driver_net_amount: int,
) -> PriceSnapshot:
    snapshot = PriceSnapshot(
        id=uuid.uuid4(),
        shipment_id=shipment_id,
        quote_id=quote_id,
        quote_version=quote_version,
        gross_amount=gross_amount,
        commission_amount=commission_amount,
        driver_net_amount=driver_net_amount,
    )
    session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)
    return snapshot
