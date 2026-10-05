---
name: pricing-service
description: >-
  Implements and extends the Asanbar freight pricing service (FastAPI, Postgres,
  Redis Streams). Use when building quotes, snapshots, idempotency, Alembic
  migrations, pricing calculations, API endpoints, or tests for this repo.
---

# Pricing Service

## Workflow (mandatory order)

1. **Plan** — write `docs/plans/<feature>.md` before any code (see `docs/plans/README.md`)
2. **Implement + test** — code and tests in the same change; run `pytest`
3. **Document** — update README, plan status, `.env.example` when done

## Before coding

1. Confirm a plan exists in `docs/plans/`
2. Read [reference.md](reference.md) for full spec details
3. Check [examples.md](examples.md) for request/response shapes
4. Respect integer IRR money — never use float or Decimal for amounts

## Implementation workflow

Per-feature checklist:

```
- [ ] Plan in docs/plans/<feature>.md
- [ ] Implementation + tests
- [ ] pytest passes
- [ ] Docs updated (README, plan status, .env.example)
```

Full project checklist:

```
Task Progress:
- [ ] Domain: rate card lookup, commission calc, money invariant
- [ ] DB: Alembic migrations (schema `pricing`), seed rate card + commission
- [ ] API: quote, latest quote, confirm-snapshot, snapshot, health/ready
- [ ] Idempotency: store keys, handle replay vs conflict
- [ ] Events: Redis stream `asanbar:events` on first confirm only
- [ ] Tests: unit math, 422 unknown card, idempotency, 409 double confirm
- [ ] README + .env.example + pyproject.toml
```

## Recommended structure

```
app/
  main.py                 # FastAPI app, routers, lifespan
  api/v1/pricing/         # route handlers
  domain/pricing.py       # pure calculation (no I/O)
  services/               # quote, snapshot, idempotency orchestration
  repositories/           # Postgres access
  events/                 # Redis stream publisher
  schemas/                # Pydantic request/response models
  errors.py               # error envelope + codes
config/
  rate_card.yaml          # seeded to Postgres
alembic/
tests/
  unit/
  integration/
```

## Key implementation rules

### Pricing (pure function)

```python
def calculate_quote(
    distance_km: int,
    stop_count: int,
    rate_per_km: int,
    stop_fee: int,
    commission_rate_bps: int,
) -> QuoteAmounts:
    distance_amount = distance_km * rate_per_km
    extra_stops = max(0, stop_count - 1)
    stop_total = stop_fee * extra_stops
    gross = distance_amount + stop_total
    commission = round(gross * commission_rate_bps / 10_000)
    driver_net = gross - commission
    assert driver_net + commission == gross
    return QuoteAmounts(gross, commission, driver_net, ...)
```

### Quote endpoint logic

1. Validate inputs (`distance_km > 0`, `stop_count >= 1`)
2. Resolve rate card; unknown → 422 `UNKNOWN_RATE_CARD`
3. If `force_recalculate` is false and matching quote exists → return it
4. Else create new quote (bump version if recalculating)

### Confirm-snapshot logic

1. Require `Idempotency-Key` header
2. Check idempotency store first (replay → 200, no event)
3. If snapshot exists for shipment → 409 `SNAPSHOT_ALREADY_EXISTS`
4. If key used for different shipment → 409 `IDEMPOTENCY_CONFLICT`
5. Load latest quote; missing → 404
6. Insert snapshot + idempotency record; publish event (201)

### Error handler

Centralize error responses:

```python
{"error": {"code": code, "message": message, "correlation_id": correlation_id}}
```

Read `X-Correlation-Id` from request; include on all error responses.

## Testing strategy

| Test | Type | Assert |
|------|------|--------|
| Commission math | unit | `driver_net + commission == gross`, all int |
| Unknown rate card | API | 422, code `UNKNOWN_RATE_CARD` |
| Idempotent confirm | integration | 2x same key → 1 snapshot, 1 stream entry |
| Double confirm | integration | 2nd confirm → 409 `SNAPSHOT_ALREADY_EXISTS` |

Use testcontainers or Docker Postgres; `fakeredis` for stream assertions.

## Deliverable checklist

- [ ] `alembic upgrade head` works on fresh DB
- [ ] Single pytest command documented in README
- [ ] `.env.example` lists all required vars
- [ ] README explains idempotency design + prod hardening ideas

## Additional resources

- Full spec: [reference.md](reference.md)
- API examples: [examples.md](examples.md)
- Project spec file: `docs/SPEC.md`
