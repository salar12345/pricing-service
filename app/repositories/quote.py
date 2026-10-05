import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quote import PricingQuote
from app.schemas.quote import ShipmentInputs


async def find_matching_quote(
    session: AsyncSession, shipment_id: str, inputs: ShipmentInputs
) -> PricingQuote | None:
    result = await session.execute(
        select(PricingQuote)
        .where(
            PricingQuote.shipment_id == shipment_id,
            PricingQuote.distance_km == inputs.distance_km,
            PricingQuote.stop_count == inputs.stop_count,
            PricingQuote.cargo_type == inputs.cargo_type,
            PricingQuote.vehicle_type == inputs.vehicle_type,
        )
        .order_by(PricingQuote.quote_version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_quote(session: AsyncSession, shipment_id: str) -> PricingQuote | None:
    result = await session.execute(
        select(PricingQuote)
        .where(PricingQuote.shipment_id == shipment_id)
        .order_by(PricingQuote.quote_version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_max_quote_version(session: AsyncSession, shipment_id: str) -> int:
    result = await session.scalar(
        select(func.max(PricingQuote.quote_version)).where(
            PricingQuote.shipment_id == shipment_id
        )
    )
    return result or 0


async def create_quote(
    session: AsyncSession,
    *,
    shipment_id: str,
    quote_version: int,
    inputs: ShipmentInputs,
    gross_amount: int,
    commission_amount: int,
    driver_net_amount: int,
    breakdown: dict,
) -> PricingQuote:
    quote = PricingQuote(
        id=uuid.uuid4(),
        shipment_id=shipment_id,
        quote_version=quote_version,
        distance_km=inputs.distance_km,
        stop_count=inputs.stop_count,
        cargo_type=inputs.cargo_type,
        vehicle_type=inputs.vehicle_type,
        gross_amount=gross_amount,
        commission_amount=commission_amount,
        driver_net_amount=driver_net_amount,
        breakdown=breakdown,
    )
    session.add(quote)
    await session.flush()
    await session.refresh(quote)
    return quote
