import uuid

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SCHEMA = "pricing"


class RateCard(Base):
    __tablename__ = "rate_cards"
    __table_args__ = (
        UniqueConstraint("cargo_type", "vehicle_type", name="uq_rate_cards_cargo_vehicle"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cargo_type: Mapped[str] = mapped_column(String(64), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(64), nullable=False)
    rate_per_km: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stop_fee: Mapped[int] = mapped_column(BigInteger, nullable=False)
