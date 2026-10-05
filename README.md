# Pricing Service

Standalone freight pricing microservice for the [Asanbar take-home assignment](docs/SPEC.md). Quotes shipments, freezes immutable price snapshots on confirm, and publishes events for downstream payment.

## Features

- Integer IRR pricing (no floats) with commission split
- Quote caching and version bumping
- Idempotent snapshot confirmation
- Redis Stream events for payment integration
- PostgreSQL persistence with Alembic migrations

## Requirements

- Python 3.11+ (3.12 recommended per spec)
- Docker (Postgres + Redis for local development)
- Docker daemon (for integration tests via testcontainers)

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
# or: pip install -e ".[dev]"

cp .env.example .env
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
pytest -v
```

Open **Swagger UI** at http://localhost:8000/docs and follow [docs/SWAGGER_TESTING.md](docs/SWAGGER_TESTING.md) to test all endpoints.

## Architecture

```
Client
  │
  ▼
FastAPI (/api/v1/pricing)
  │
  ├── QuoteService        → POST quote, GET latest quote
  └── SnapshotService     → POST confirm-snapshot, GET snapshot
         │
    ┌────┴────┐
    ▼         ▼
PostgreSQL   Redis Streams
 (pricing)   (asanbar:events)
```

### Project layout

```
app/
  api/v1/pricing.py      # HTTP routes
  domain/pricing.py      # Pure pricing math (no I/O)
  services/              # Quote & snapshot orchestration
  repositories/          # Database access
  events/publisher.py    # Redis stream publisher
  models/                # SQLAlchemy ORM
alembic/                 # Migrations (schema: pricing)
config/rate_card.yaml    # Seed source for rate cards
tests/                   # Unit + integration tests
```

### Layering

| Layer | Responsibility |
|-------|----------------|
| `api/` | HTTP, headers, status codes |
| `services/` | Business rules, transactions |
| `domain/` | Integer pricing calculations |
| `repositories/` | SQL queries |
| `events/` | Outbound Redis events (after commit) |

## API

Base path: `/api/v1/pricing`

### Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/health` | 200 | Process alive |
| GET | `/ready` | 200/503 | Postgres reachable |
| POST | `/shipments/{id}/quote` | 201/200 | Create or return cached quote |
| GET | `/shipments/{id}/quotes/latest` | 200/404 | Latest quote |
| POST | `/shipments/{id}/confirm-snapshot` | 201/200/404/409 | Freeze latest quote |
| GET | `/shipments/{id}/snapshot` | 200/404 | Confirmed snapshot |

### Error format

All errors return:

```json
{
  "error": {
    "code": "QUOTE_NOT_FOUND",
    "message": "...",
    "correlation_id": "..."
  }
}
```

Pass `X-Correlation-Id` on requests to trace errors.

| Code | HTTP | When |
|------|------|------|
| `VALIDATION_ERROR` | 422 | Invalid input |
| `UNKNOWN_RATE_CARD` | 422 | Unknown cargo/vehicle combo |
| `QUOTE_NOT_FOUND` | 404 | No quote for shipment |
| `SNAPSHOT_NOT_FOUND` | 404 | No confirmed snapshot |
| `SNAPSHOT_ALREADY_EXISTS` | 409 | Second confirm on same shipment |
| `IDEMPOTENCY_CONFLICT` | 409 | Same key used for different shipment |

### End-to-end example

```bash
# 1. Create quote (201)
curl -s -X POST http://localhost:8000/api/v1/pricing/shipments/shp-001/quote \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "distance_km": 450,
      "stop_count": 2,
      "cargo_type": "general",
      "vehicle_type": "trailer"
    },
    "force_recalculate": false
  }'

# Expected: gross_amount=5900000, commission_amount=590000, driver_net_amount=5310000

# 2. Confirm snapshot (201) — requires Idempotency-Key
curl -s -X POST http://localhost:8000/api/v1/pricing/shipments/shp-001/confirm-snapshot \
  -H "Idempotency-Key: idem-key-001"

# 3. Replay confirm (200, same snapshot, no new Redis event)
curl -s -X POST http://localhost:8000/api/v1/pricing/shipments/shp-001/confirm-snapshot \
  -H "Idempotency-Key: idem-key-001"

# 4. Get snapshot
curl -s http://localhost:8000/api/v1/pricing/shipments/shp-001/snapshot

# 5. Inspect Redis event
docker compose exec redis redis-cli XRANGE asanbar:events - +
```

## Pricing logic

Rate cards (seeded from `config/rate_card.yaml`):

| cargo_type | vehicle_type | rate/km | stop fee |
|------------|--------------|---------|----------|
| general | trailer | 12,000 | 500,000 |
| general | single | 10,000 | 400,000 |
| refrigerated | trailer | 15,000 | 600,000 |

```
gross = distance_km × rate_per_km + stop_fee × max(0, stop_count - 1)
commission = round(gross × commission_rate_bps / 10_000)
driver_net = gross - commission
```

Invariant: `driver_net + commission == gross` (all integers, IRR).

Default commission: 10% (`commission_rate_bps = 1000`).

## Idempotency design

Confirm-snapshot requires an `Idempotency-Key` header. Decision order:

1. **Replay** — key already used for this shipment → return stored snapshot (200), no new Redis event
2. **Conflict** — key used for a different shipment → 409 `IDEMPOTENCY_CONFLICT`
3. **Duplicate** — snapshot already exists for shipment → 409 `SNAPSHOT_ALREADY_EXISTS`
4. **Missing quote** — no quote to freeze → 404 `QUOTE_NOT_FOUND`
5. **First success** — create snapshot + idempotency record, publish event (201)

Implementation details:

- Idempotency records stored in `pricing.idempotency_keys` with unique `(key, shipment_id)`
- Lookup by key alone detects cross-shipment conflicts
- One snapshot per shipment enforced by unique constraint on `price_snapshots.shipment_id`
- Redis event published **after** DB commit to avoid orphan events

## Redis events

Stream: `asanbar:events`  
Field: `payload` (JSON)

Published only on first successful confirm (not on idempotent replay):

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

Schema: `pricing`

| Table | Purpose |
|-------|---------|
| `rate_cards` | cargo/vehicle → rates (from YAML seed) |
| `commission_rules` | Active commission config |
| `pricing_quotes` | Quotes with version and denormalized inputs |
| `price_snapshots` | One immutable snapshot per shipment |
| `idempotency_keys` | Confirm replay tracking |

```bash
alembic upgrade head    # apply migrations + seed
alembic downgrade -1    # rollback one revision
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://pricing:pricing@localhost:5432/pricing` | Async Postgres URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL for event publishing |
| `LOG_LEVEL` | `info` | Log level |

Copy `.env.example` to `.env` and adjust as needed.

## Run tests

```bash
pytest -v
```

| Suite | What it uses |
|-------|--------------|
| Unit (`tests/unit/`) | Pure pricing math, no external services |
| Integration (`tests/integration/`) | testcontainers Postgres + fakeredis |

Minimum spec coverage (all implemented):

- Commission math + money invariant
- Unknown rate card → 422
- Idempotent confirm → one snapshot, one Redis event
- Double confirm → 409
- Confirm without quote → 404
- Idempotency conflict → 409
- Health / ready probes

## Production hardening (not implemented)

Ideas for a production deployment:

| Area | Recommendation |
|------|----------------|
| Auth | JWT or API gateway auth; this exercise skips auth |
| Idempotency | TTL on idempotency keys; periodic cleanup job |
| Events | Outbox pattern if Redis publish fails; dead-letter stream |
| Observability | Structured JSON logs, correlation IDs, metrics on quote/confirm latency |
| Database | Connection pooling tuning, read replicas for quote lookups |
| Concurrency | Handle `IntegrityError` on snapshot unique constraint as 409 |
| Rate limiting | Gateway-level throttling on quote/confirm endpoints |
| Secrets | Vault/K8s secrets for DB and Redis URLs |

## Out of scope

Per the take-home spec: JWT auth, commission admin CRUD, event consumers, K8s/CI, payment integration.

## Documentation

- [docs/SPEC.md](docs/SPEC.md) — original requirements
- [docs/SWAGGER_TESTING.md](docs/SWAGGER_TESTING.md) — step-by-step Swagger UI testing guide
- [docs/plans/implementation.md](docs/plans/implementation.md) — implementation plan

## Implementation status

All phases complete.

- [x] Phase 1 — Scaffold, DB, health/ready
- [x] Phase 2 — Quote API
- [x] Phase 3 — Snapshot & idempotency
- [x] Phase 4 — Redis events
- [x] Phase 5 — Documentation polish
