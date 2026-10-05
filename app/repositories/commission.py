from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission_rule import CommissionRule


async def get_active_commission_rule(session: AsyncSession) -> CommissionRule | None:
    result = await session.execute(
        select(CommissionRule).where(
            CommissionRule.name == "default",
            CommissionRule.active.is_(True),
        )
    )
    return result.scalar_one_or_none()
