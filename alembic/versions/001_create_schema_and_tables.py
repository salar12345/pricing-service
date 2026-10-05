"""create schema and tables

Revision ID: 001
Revises:
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "pricing"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    op.create_table(
        "rate_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cargo_type", sa.String(64), nullable=False),
        sa.Column("vehicle_type", sa.String(64), nullable=False),
        sa.Column("rate_per_km", sa.BigInteger(), nullable=False),
        sa.Column("stop_fee", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("cargo_type", "vehicle_type", name="uq_rate_cards_cargo_vehicle"),
        schema=SCHEMA,
    )

    op.create_table(
        "commission_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("commission_rate_bps", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        schema=SCHEMA,
    )

    op.create_table(
        "pricing_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", sa.String(128), nullable=False),
        sa.Column("quote_version", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Integer(), nullable=False),
        sa.Column("stop_count", sa.Integer(), nullable=False),
        sa.Column("cargo_type", sa.String(64), nullable=False),
        sa.Column("vehicle_type", sa.String(64), nullable=False),
        sa.Column("gross_amount", sa.BigInteger(), nullable=False),
        sa.Column("commission_amount", sa.BigInteger(), nullable=False),
        sa.Column("driver_net_amount", sa.BigInteger(), nullable=False),
        sa.Column("breakdown", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pricing_quotes_shipment_id",
        "pricing_quotes",
        ["shipment_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pricing_quotes_shipment_version",
        "pricing_quotes",
        ["shipment_id", "quote_version"],
        schema=SCHEMA,
    )

    op.create_table(
        "price_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", sa.String(128), nullable=False, unique=True),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_version", sa.Integer(), nullable=False),
        sa.Column("gross_amount", sa.BigInteger(), nullable=False),
        sa.Column("commission_amount", sa.BigInteger(), nullable=False),
        sa.Column("driver_net_amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["quote_id"], [f"{SCHEMA}.pricing_quotes.id"]),
        schema=SCHEMA,
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("shipment_id", sa.String(128), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("key", "shipment_id", name="uq_idempotency_key_shipment"),
        sa.ForeignKeyConstraint(["snapshot_id"], [f"{SCHEMA}.price_snapshots.id"]),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys", schema=SCHEMA)
    op.drop_table("price_snapshots", schema=SCHEMA)
    op.drop_index("ix_pricing_quotes_shipment_version", table_name="pricing_quotes", schema=SCHEMA)
    op.drop_index("ix_pricing_quotes_shipment_id", table_name="pricing_quotes", schema=SCHEMA)
    op.drop_table("pricing_quotes", schema=SCHEMA)
    op.drop_table("commission_rules", schema=SCHEMA)
    op.drop_table("rate_cards", schema=SCHEMA)
    op.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
