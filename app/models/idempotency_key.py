import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SCHEMA = "pricing"


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("key", "shipment_id", name="uq_idempotency_key_shipment"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    shipment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.price_snapshots.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
