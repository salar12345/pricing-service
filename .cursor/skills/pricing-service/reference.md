# Pricing Service Reference

## Technology choices

| Component | Requirement |
|-----------|-------------|
| Python | 3.12 |
| Framework | FastAPI |
| Database | PostgreSQL, schema `pricing` |
| Migrations | Alembic |
| Events | Redis Streams |
| Testing | pytest |

## Database tables (suggested)

Explain actual names in README. Typical entities:

- **rate_cards** — cargo_type, vehicle_type, rate_per_km, stop_fee (from YAML seed)
- **commission_rules** — name, commission_rate_bps, active flag
- **pricing_quotes** — shipment_id, quote_version, inputs hash/json, amounts, created_at
- **price_snapshots** — shipment_id (unique), quote_id, amounts, confirmed_at
- **idempotency_keys** — key, shipment_id, snapshot_id, created_at (for replay detection)

## Idempotency design notes

Store `Idempotency-Key` + operation context (shipment_id, endpoint). On replay:
- Return stored snapshot with 200
- Do **not** publish a second Redis event

Conflict when same key maps to different shipment_id → 409.

## Redis stream format

- Stream name: `asanbar:events`
- Single field: `payload` (JSON string)
- Publish only on first successful confirm (not idempotent replay)

Event schema:

```json
{
  "event_id": "<uuid>",
  "event_type": "price_snapshot.created",
  "occurred_at": "<iso8601>",
  "correlation_id": null,
  "data": {
    "shipment_id": "...",
    "price_snapshot_id": "...",
    "quote_id": "...",
    "gross_amount": 0,
    "commission_amount": 0,
    "driver_net_amount": 0,
    "currency": "IRR"
  }
}
```

## Environment variables (typical)

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/pricing
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=info
```

## Health endpoints

- `GET /health` — always 200 if process running
- `GET /ready` — 200 if Postgres reachable, 503 otherwise

## Out of scope

Do not implement: JWT/auth, commission admin CRUD, event consumers, K8s/CI, payment integration.

Optional extras (mention in README if added): admin override, consumer stub.

## Prod hardening ideas (for README)

- Real Redis persistence and monitoring
- Idempotency key TTL and cleanup
- Rate limiting and auth at gateway
- Structured logging with correlation IDs
- DB connection pooling and read replicas
- Dead-letter handling for failed event publishes
