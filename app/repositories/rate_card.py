from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_card import RateCard


async def get_rate_card(
    session: AsyncSession, cargo_type: str, vehicle_type: str
) -> RateCard | None:
    result = await session.execute(
        select(RateCard).where(
            RateCard.cargo_type == cargo_type,
            RateCard.vehicle_type == vehicle_type,
        )
    )
    return result.scalar_one_or_none()
