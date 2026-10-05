import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SCHEMA = "pricing"


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.pricing_quotes.id"),
        nullable=False,
    )
    quote_version: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    commission_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    driver_net_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
