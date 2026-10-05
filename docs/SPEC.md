# Pricing Service — Take-home Specification

Source: Asanbar engineering take-home assignment.

## Flow

1. Client posts shipment inputs → service returns quote (gross, commission, driver net).
2. Client confirms → latest quote becomes immutable snapshot.
3. Confirm publishes `price_snapshot.created` on Redis stream for payment.

## Stack

- Python 3.12, FastAPI, PostgreSQL (schema `pricing`), Alembic, Redis Streams, pytest
- API under `/api/v1/pricing`
- `GET /health`, `GET /ready` (ready checks DB)
- No auth/JWT

## Money

- IRR as integers only. No floats, no Decimal.
- Invariant: `driver_net_amount + commission_amount == gross_amount`

## Pricing logic

Rate card (YAML, seeded to Postgres):

| cargo_type | vehicle_type | rate_per_km | stop_fee |
|------------|--------------|-------------|----------|
| general | trailer | 12_000 | 500_000 |
| general | single | 10_000 | 400_000 |
| refrigerated | trailer | 15_000 | 600_000 |

Unknown combo → 422 `UNKNOWN_RATE_CARD`.

```
base = distance_km * rate_per_km + stop_fee * max(0, stop_count - 1)
gross = base
commission = round(gross * commission_rate_bps / 10_000)
driver_net = gross - commission
```

Commission rule seed: name `"default"`, `commission_rate_bps = 1000`, active.

Validation: `distance_km > 0`, `stop_count >= 1`.

## Endpoints

### Error format

```json
{
  "error": {
    "code": "QUOTE_NOT_FOUND",
    "message": "...",
    "correlation_id": "..."
  }
}
```

Pass through `X-Correlation-Id` when sent by client.

### POST `/api/v1/pricing/shipments/{shipment_id}/quote`

Request:

```json
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

- `force_recalculate: false` — same shipment + inputs → existing quote (same `quote_id`)
- `force_recalculate: true` — bump `quote_version`

Response includes `quote_id`, amounts, `breakdown`, `created_at`.

Example for 450 km, 2 stops, general+trailer:
- distance_amount = 450 * 12000 = 5_400_000
- stop_fee = 500_000 (one extra stop)
- gross = 5_900_000, commission = 590_000, driver_net = 5_310_000

### GET `/api/v1/pricing/shipments/{shipment_id}/quotes/latest`

Latest quote or 404 `QUOTE_NOT_FOUND`.

### POST `/api/v1/pricing/shipments/{shipment_id}/confirm-snapshot`

Requires `Idempotency-Key` header.

| Case | Status |
|------|--------|
| No quote | 404 `QUOTE_NOT_FOUND` |
| Snapshot already exists | 409 `SNAPSHOT_ALREADY_EXISTS` |
| Same idempotency key replay | 200, same snapshot, no second event |
| Same key, different context | 409 `IDEMPOTENCY_CONFLICT` |
| First success | 201, snapshot + event |

### GET `/api/v1/pricing/shipments/{shipment_id}/snapshot`

Confirmed snapshot or 404 `SNAPSHOT_NOT_FOUND`.

## Redis event (first confirm only)

Stream: `asanbar:events`. Field `payload` (JSON):

```json
{
  "event_id": "...",
  "event_type": "price_snapshot.created",
  "occurred_at": "2026-06-10T12:05:00+00:00",
  "correlation_id": null,
  "data": {
    "shipment_id": "...",
    "price_snapshot_id": "...",
    "quote_id": "...",
    "gross_amount": 5900000,
    "commission_amount": 590000,
    "driver_net_amount": 5310000,
    "currency": "IRR"
  }
}
```

## Database

Schema `pricing`. Suggested tables: quotes, snapshots, idempotency keys, commission rules, rate cards. Unique constraint: one snapshot per shipment. Alembic migrations required.

## Deliverables

- Code: `app/`, `tests/`, `alembic/`
- README: setup, env vars, run app, run tests, idempotency notes, prod hardening ideas
- `.env.example`, `pyproject.toml`
- Optional: docker-compose for Postgres/Redis

## Out of scope

JWT, commission admin CRUD, event consumers, K8s/CI, payment integration.
