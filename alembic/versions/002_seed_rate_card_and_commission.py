"""seed rate card and commission

Revision ID: 002
Revises: 001
Create Date: 2026-06-10

"""

from pathlib import Path
from typing import Sequence, Union
from uuid import uuid4

import yaml
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "pricing"
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "rate_card.yaml"


def upgrade() -> None:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rate_cards_table = sa.table(
        "rate_cards",
        sa.column("id", sa.UUID()),
        sa.column("cargo_type", sa.String()),
        sa.column("vehicle_type", sa.String()),
        sa.column("rate_per_km", sa.BigInteger()),
        sa.column("stop_fee", sa.BigInteger()),
        schema=SCHEMA,
    )
    op.bulk_insert(
        rate_cards_table,
        [
            {
                "id": uuid4(),
                "cargo_type": row["cargo_type"],
                "vehicle_type": row["vehicle_type"],
                "rate_per_km": row["rate_per_km"],
                "stop_fee": row["stop_fee"],
            }
            for row in data["rate_cards"]
        ],
    )

    commission_table = sa.table(
        "commission_rules",
        sa.column("id", sa.UUID()),
        sa.column("name", sa.String()),
        sa.column("commission_rate_bps", sa.Integer()),
        sa.column("active", sa.Boolean()),
        schema=SCHEMA,
    )
    op.bulk_insert(
        commission_table,
        [
            {
                "id": uuid4(),
                "name": rule["name"],
                "commission_rate_bps": rule["commission_rate_bps"],
                "active": rule["active"],
            }
            for rule in data["commission_rules"]
        ],
    )


def downgrade() -> None:
    op.execute(sa.text(f"DELETE FROM {SCHEMA}.rate_cards"))
    op.execute(sa.text(f"DELETE FROM {SCHEMA}.commission_rules"))
