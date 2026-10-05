import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idempotency_key import IdempotencyKey


async def get_by_key(session: AsyncSession, key: str) -> IdempotencyKey | None:
    result = await session.execute(select(IdempotencyKey).where(IdempotencyKey.key == key))
    return result.scalar_one_or_none()


async def create_idempotency_key(
    session: AsyncSession,
    *,
    key: str,
    shipment_id: str,
    snapshot_id: uuid.UUID,
) -> IdempotencyKey:
    record = IdempotencyKey(
        id=uuid.uuid4(),
        key=key,
        shipment_id=shipment_id,
        snapshot_id=snapshot_id,
    )
    session.add(record)
    await session.flush()
    return record
