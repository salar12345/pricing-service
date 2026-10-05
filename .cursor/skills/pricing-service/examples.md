# API Examples

## POST quote

**Request:**

```http
POST /api/v1/pricing/shipments/shp-001/quote
Content-Type: application/json

{
  "inputs": {
    "distance_km": 450,
    "stop_count": 2,
    "cargo_type": "general",
    "vehicle_type": "trailer"
  },
  "force_recalculate": false
}
```

**Response (201 or 200):**

```json
{
  "quote_id": "qte-abc123",
  "shipment_id": "shp-001",
  "quote_version": 1,
  "inputs": {
    "distance_km": 450,
    "stop_count": 2,
    "cargo_type": "general",
    "vehicle_type": "trailer"
  },
  "gross_amount": 5900000,
  "commission_amount": 590000,
  "driver_net_amount": 5310000,
  "currency": "IRR",
  "breakdown": {
    "base_amount": 5900000,
    "distance_amount": 5400000,
    "stop_fee": 500000,
    "rate_per_km": 12000,
    "commission_rate_bps": 1000
  },
  "created_at": "2026-06-10T12:00:00+00:00"
}
```

**Calculation:** 450 × 12_000 + 1 × 500_000 = 5_900_000 gross; 10% commission = 590_000.

## Unknown rate card

```http
POST /api/v1/pricing/shipments/shp-002/quote
```

Body with `"cargo_type": "hazmat"` → **422:**

```json
{
  "error": {
    "code": "UNKNOWN_RATE_CARD",
    "message": "No rate card for cargo_type=hazmat, vehicle_type=trailer",
    "correlation_id": "req-xyz"
  }
}
```

## Confirm snapshot (first time)

```http
POST /api/v1/pricing/shipments/shp-001/confirm-snapshot
Idempotency-Key: idem-key-001
```

**Response (201):**

```json
{
  "snapshot_id": "snap-def456",
  "shipment_id": "shp-001",
  "quote_id": "qte-abc123",
  "quote_version": 1,
  "gross_amount": 5900000,
  "commission_amount": 590000,
  "driver_net_amount": 5310000,
  "currency": "IRR",
  "confirmed_at": "2026-06-10T12:05:00+00:00"
}
```

## Confirm replay (same idempotency key)

Same request again → **200**, identical snapshot body, **no new Redis event**.

## Second confirm (different key, snapshot exists)

```http
POST /api/v1/pricing/shipments/shp-001/confirm-snapshot
Idempotency-Key: idem-key-002
```

→ **409:**

```json
{
  "error": {
    "code": "SNAPSHOT_ALREADY_EXISTS",
    "message": "Snapshot already confirmed for shipment shp-001",
    "correlation_id": null
  }
}
```

## GET latest quote / snapshot

```http
GET /api/v1/pricing/shipments/shp-001/quotes/latest
GET /api/v1/pricing/shipments/shp-001/snapshot
```

404 with `QUOTE_NOT_FOUND` or `SNAPSHOT_NOT_FOUND` when missing.
