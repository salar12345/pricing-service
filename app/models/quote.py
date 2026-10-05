import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SCHEMA = "pricing"


class PricingQuote(Base):
    __tablename__ = "pricing_quotes"
    __table_args__ = (
        Index("ix_pricing_quotes_shipment_version", "shipment_id", "quote_version"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    quote_version: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_km: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cargo_type: Mapped[str] = mapped_column(String(64), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(64), nullable=False)
    gross_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    commission_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    driver_net_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
