from datetime import datetime

from pydantic import BaseModel, Field


class ShipmentInputs(BaseModel):
    distance_km: int = Field(gt=0)
    stop_count: int = Field(ge=1)
    cargo_type: str
    vehicle_type: str


class QuoteRequest(BaseModel):
    inputs: ShipmentInputs
    force_recalculate: bool = False


class QuoteBreakdownResponse(BaseModel):
    base_amount: int
    distance_amount: int
    stop_fee: int
    rate_per_km: int
    commission_rate_bps: int


class QuoteResponse(BaseModel):
    quote_id: str
    shipment_id: str
    quote_version: int
    inputs: ShipmentInputs
    gross_amount: int
    commission_amount: int
    driver_net_amount: int
    currency: str = "IRR"
    breakdown: QuoteBreakdownResponse
    created_at: datetime
