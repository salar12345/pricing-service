from datetime import datetime

from pydantic import BaseModel


class SnapshotResponse(BaseModel):
    snapshot_id: str
    shipment_id: str
    quote_id: str
    quote_version: int
    gross_amount: int
    commission_amount: int
    driver_net_amount: int
    currency: str = "IRR"
    confirmed_at: datetime
