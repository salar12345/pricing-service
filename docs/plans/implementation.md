# Pricing Service — Full Implementation Plan

## Status

**done**

## Goal

Build a standalone Python pricing microservice per `docs/SPEC.md`: quote shipments, confirm immutable snapshots, publish Redis events. Deliver runnable app, migrations, tests, and README within the take-home scope.

## Scope

### In scope

- FastAPI app with all spec endpoints under `/api/v1/pricing`
- PostgreSQL schema `pricing` with Alembic migrations + seed data
- Rate card from YAML seeded to DB; commission rule seed
- Integer IRR pricing math with invariant checks
- Quote caching and version bumping
- Idempotent confirm-snapshot with Redis stream event (first success only)
- Health/ready probes
- pytest suite (unit + integration)
- `docker-compose.yml` for Postgres + Redis
- README, `.env.example`, `pyproject.toml`

### Out of scope

- JWT/auth, commission admin CRUD, event consumers, K8s/CI, payment integration

---

## Architecture

```
Client
  │
  ▼
FastAPI (app/main.py)
  ├── /health, /ready
  └── /api/v1/pricing/*
        │
        ▼
   Services (orchestration)
   ├── QuoteService
   ├── SnapshotService
   └── IdempotencyService
        │
   ┌────┴────┐
   ▼         ▼
Postgres   Redis Streams
(pricing)  (asanbar:events)
```

### Layer responsibilities

| Layer | Role |
|-------|------|
| `app/api/` | HTTP routing, request/response mapping, header extraction |
| `app/schemas/` | Pydantic models for API contracts |
| `app/domain/pricing.py` | Pure pricing math — no I/O |
| `app/services/` | Business rules: quote reuse, confirm, idempotency |
| `app/repositories/` | SQLAlchemy queries |
| `app/events/` | Redis stream publisher |
| `app/errors.py` | Error codes, exception classes, handler |

---

## Project layout

```
pricing-service/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, lifespan, middleware
│   ├── config.py                  # Settings from env (pydantic-settings)
│   ├── db.py                      # Engine, session factory
│   ├── errors.py                  # AppError, error handler
│   ├── api/
│   │   ├── deps.py                # DB session, correlation_id deps
│   │   └── v1/
│   │       ├── router.py
│   │       └── pricing.py         # All pricing endpoints
│   ├── domain/
│   │   └── pricing.py             # calculate_quote(), input validation
│   ├── schemas/
│   │   ├── quote.py
│   │   ├── snapshot.py
│   │   └── error.py
│   ├── models/                    # SQLAlchemy ORM
│   │   ├── rate_card.py
│   │   ├── commission_rule.py
│   │   ├── quote.py
│   │   ├── snapshot.py
│   │   └── idempotency_key.py
│   ├── repositories/
│   │   ├── rate_card.py
│   │   ├── commission.py
│   │   ├── quote.py
│   │   ├── snapshot.py
│   │   └── idempotency.py
│   ├── services/
│   │   ├── quote_service.py
│   │   └── snapshot_service.py
│   └── events/
│       └── publisher.py
├── config/
│   └── rate_card.yaml
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 001_create_schema_and_tables.py
│       └── 002_seed_rate_card_and_commission.py
├── tests/
│   ├── conftest.py                # fixtures: db, client, fakeredis
│   ├── unit/
│   │   └── test_pricing_math.py
│   └── integration/
│       ├── test_quote_api.py
│       ├── test_snapshot_api.py
│       └── test_health.py
├── docs/
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Database schema

Schema: `pricing`

### `rate_cards`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| cargo_type | VARCHAR | e.g. `general`, `refrigerated` |
| vehicle_type | VARCHAR | e.g. `trailer`, `single` |
| rate_per_km | BIGINT | IRR integer |
| stop_fee | BIGINT | IRR integer |

Unique: `(cargo_type, vehicle_type)`

### `commission_rules`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| name | VARCHAR UNIQUE | seed: `default` |
| commission_rate_bps | INTEGER | seed: `1000` |
| active | BOOLEAN | seed: `true` |

### `pricing_quotes`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | `quote_id` in API |
| shipment_id | VARCHAR | indexed |
| quote_version | INTEGER | 1, 2, 3… per shipment |
| distance_km | INTEGER | denormalized inputs |
| stop_count | INTEGER | |
| cargo_type | VARCHAR | |
| vehicle_type | VARCHAR | |
| gross_amount | BIGINT | |
| commission_amount | BIGINT | |
| driver_net_amount | BIGINT | |
| breakdown | JSONB | distance_amount, stop_fee, rate_per_km, etc. |
| created_at | TIMESTAMPTZ | |

Index: `(shipment_id, quote_version DESC)` for latest lookup.

**Quote reuse logic:** When `force_recalculate=false`, find latest quote for shipment where all four input fields match → return same row (same `quote_id`). Otherwise insert new row with `quote_version = max(existing) + 1` (or 1 if first).

### `price_snapshots`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | `snapshot_id` in API |
| shipment_id | VARCHAR UNIQUE | one snapshot per shipment |
| quote_id | UUID FK | |
| quote_version | INTEGER | |
| gross_amount | BIGINT | frozen from quote |
| commission_amount | BIGINT | |
| driver_net_amount | BIGINT | |
| confirmed_at | TIMESTAMPTZ | |

### `idempotency_keys`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| key | VARCHAR | from `Idempotency-Key` header |
| shipment_id | VARCHAR | operation context |
| snapshot_id | UUID FK | result of successful confirm |
| created_at | TIMESTAMPTZ | |

Unique: `(key, shipment_id)` — same key + same shipment = replay.

**Conflict detection:** If key exists with different `shipment_id` → 409 `IDEMPOTENCY_CONFLICT`.

---

## Domain logic

### Input validation (Pydantic + domain)

- `distance_km > 0` → 422 validation error
- `stop_count >= 1` → 422 validation error
- Unknown `(cargo_type, vehicle_type)` → 422 `UNKNOWN_RATE_CARD`

### Pricing calculation (`app/domain/pricing.py`)

```python
distance_amount = distance_km * rate_per_km
stop_total = stop_fee * max(0, stop_count - 1)
gross = distance_amount + stop_total
commission = round(gross * commission_rate_bps / 10_000)
driver_net = gross - commission
# invariant: driver_net + commission == gross
```

All values `int`. Unit tests cover edge cases and invariant.

### Active commission rule

Load single active rule named `default` at quote time. No admin API.

---

## API design

### Error handling

Global exception handler returns:

```json
{"error": {"code": "...", "message": "...", "correlation_id": "..."}}
```

Dependency reads `X-Correlation-Id` header; passes through on errors.

### Endpoints

| Method | Path | Status | Notes |
|--------|------|--------|-------|
| GET | `/health` | 200 | Process alive |
| GET | `/ready` | 200/503 | Postgres ping |
| POST | `/api/v1/pricing/shipments/{id}/quote` | 200/201 | Create or return cached |
| GET | `/api/v1/pricing/shipments/{id}/quotes/latest` | 200/404 | |
| POST | `/api/v1/pricing/shipments/{id}/confirm-snapshot` | 201/200/404/409 | Requires `Idempotency-Key` |
| GET | `/api/v1/pricing/shipments/{id}/snapshot` | 200/404 | |

### Confirm-snapshot decision tree

```
1. Idempotency-Key missing? → 422 (validation)
2. Key exists for THIS shipment? → 200 + stored snapshot (no event)
3. Key exists for DIFFERENT shipment? → 409 IDEMPOTENCY_CONFLICT
4. Snapshot exists for shipment? → 409 SNAPSHOT_ALREADY_EXISTS
5. No latest quote? → 404 QUOTE_NOT_FOUND
6. Else → create snapshot, store idempotency, publish event → 201
```

All steps in a single DB transaction where possible; publish Redis after commit.

---

## Redis event

- Stream: `asanbar:events`
- Field: `payload` (JSON string)
- Publish only on step 6 above (first successful confirm, not replay)
- Use `fakeredis` in tests; real Redis in docker-compose for local dev

Event payload per spec: `event_id`, `event_type`, `occurred_at`, `correlation_id`, `data`.

---

## Dependencies (`pyproject.toml`)

| Package | Purpose |
|---------|---------|
| fastapi | API framework |
| uvicorn[standard] | ASGI server |
| sqlalchemy[asyncio] | ORM |
| asyncpg | Postgres driver |
| alembic | Migrations |
| pydantic-settings | Config |
| redis | Redis Streams |
| pyyaml | Rate card file |
| pytest, pytest-asyncio | Testing |
| httpx | Async test client |
| testcontainers[postgres] | Integration DB |
| fakeredis | Redis in tests |

---

## Implementation phases

Execute in order. Each phase: implement → test → update docs section in README.

### Phase 1 — Scaffold & infrastructure

- [x] `pyproject.toml`, `.env.example`, `docker-compose.yml`
- [x] `app/config.py`, `app/db.py`, `app/main.py` with `/health`, `/ready`
- [x] Alembic init, migration `001` (schema + tables)
- [x] `config/rate_card.yaml`, migration `002` (seed rate card + commission)
- [x] Tests: health/ready, DB connectivity

**Deliverable:** `docker compose up -d && alembic upgrade head && uvicorn app.main:app` works.

### Phase 2 — Domain & quote API

- [x] `app/domain/pricing.py` with pure calculation
- [x] Repositories: rate_card, commission, quote
- [x] `QuoteService` with reuse + version bump logic
- [x] POST quote, GET latest quote endpoints
- [x] Error handler + correlation ID
- [x] Tests: unit math, unknown rate card 422, quote reuse, force_recalculate

**Deliverable:** Can quote a shipment end-to-end via API.

### Phase 3 — Snapshot & idempotency

- [x] Repositories: snapshot, idempotency
- [x] `SnapshotService` with full decision tree
- [x] POST confirm-snapshot, GET snapshot endpoints
- [x] Tests: idempotent replay (1 snapshot, 1 event), double confirm 409, no quote 404, idempotency conflict 409

**Deliverable:** Full quote → confirm → snapshot flow works.

### Phase 4 — Redis events

- [x] `app/events/publisher.py`
- [x] Wire into SnapshotService (post-commit publish)
- [x] Tests: assert exactly one stream entry on first confirm; zero on replay

**Deliverable:** Events visible in Redis after confirm.

### Phase 5 — Documentation & polish

- [x] README: setup, env vars, run app, run tests, architecture overview
- [x] README: idempotency design explanation
- [x] README: prod hardening notes (auth gateway, key TTL, DLQ, observability)
- [x] Mark this plan `done`
- [x] Final full pytest run

---

## Test plan (minimum required by spec)

| # | Type | Test | Assert |
|---|------|------|--------|
| 1 | unit | `test_commission_math` | `driver_net + commission == gross`, all int |
| 2 | unit | `test_commission_rounding` | round behavior at boundary values |
| 3 | integration | `test_unknown_rate_card_returns_422` | code `UNKNOWN_RATE_CARD` |
| 4 | integration | `test_quote_example_from_spec` | 450km, 2 stops → gross 5_900_000 |
| 5 | integration | `test_confirm_idempotent_replay` | 2x same key → 1 snapshot, 1 Redis event |
| 6 | integration | `test_confirm_twice_different_key` | 2nd → 409 `SNAPSHOT_ALREADY_EXISTS` |
| 7 | integration | `test_confirm_no_quote` | 404 `QUOTE_NOT_FOUND` |
| 8 | integration | `test_idempotency_conflict` | same key, different shipment → 409 |
| 9 | integration | `test_health_and_ready` | 200 / 503 behavior |

Run command (target): `pytest -v`

---

## Environment variables

```env
DATABASE_URL=postgresql+asyncpg://pricing:pricing@localhost:5432/pricing
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=info
```

---

## Key design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| DB access | SQLAlchemy 2.0 async | Fits FastAPI async; testcontainers support |
| Quote reuse | Match denormalized input columns | Simple query, no hash needed |
| Idempotency scope | `(key, shipment_id)` unique | Matches spec replay semantics |
| Event publish | After DB commit | Avoid orphan events on rollback |
| Redis in tests | fakeredis | No extra container; document in README |
| Postgres in tests | testcontainers | Real SQL, matches prod |
| UUID generation | `uuid4` in app layer | Readable IDs in API responses |

---

## Files to create (summary)

~35 files across `app/`, `alembic/`, `tests/`, `config/`, root config files. See project layout above.

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Integer rounding edge cases | Unit tests with odd gross amounts |
| Race on double confirm | DB unique on `shipment_id`; handle IntegrityError → 409 |
| Event published but DB rolled back | Publish after commit only |
| testcontainers slow | Scope integration tests; keep unit tests fast |

---

## Notes

- Plan must be approved before Phase 1 coding starts.
- After each phase, update README and check off phase items here.
- Deviations from this plan should be recorded in this file under a "Deviations" section.

## Deviations

- **Python version**: `pyproject.toml` requires `>=3.11` (dev environment has 3.11; spec targets 3.12).
- **Alembic**: `env.py` creates `pricing` schema before version table (required when `version_table_schema="pricing"`).
