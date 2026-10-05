# Swagger Testing Guide

Step-by-step guide to test the Pricing Service using Swagger UI (`/docs`).

## Before you start

### 1. Start dependencies

```bash
docker compose up -d
alembic upgrade head
```

### 2. Start the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

If port 8000 is busy, use another port (e.g. `8001`) and open Swagger at that port.

### 3. Open Swagger

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | Swagger UI (interactive) |
| http://localhost:8000/redoc | ReDoc (read-only) |

Replace `8000` with your port if different.

### 4. Verify the service is ready

In Swagger, expand **default** and run:

1. **GET `/health`** → expect `200` and `{"status":"ok"}`
2. **GET `/ready`** → expect `200` and `{"status":"ready"}`

If `/ready` returns `503`, Postgres is not reachable. Check `docker compose ps` and `DATABASE_URL` in `.env`.

---

## Recommended test flow

Use one `shipment_id` for the whole flow, e.g. `shp-swagger-001`.

```
health/ready → quote → latest quote → confirm → snapshot → (optional) replay confirm
```

---

## Step 1 — Create a quote

**Endpoint:** `POST /api/v1/pricing/shipments/{shipment_id}/quote`  
**Tag:** `pricing`

1. Click **Try it out**
2. Set `shipment_id` = `shp-swagger-001`
3. Request body:

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

4. Click **Execute**

**Expected:** `201 Created`

| Field | Expected value |
|-------|----------------|
| `gross_amount` | `5900000` |
| `commission_amount` | `590000` |
| `driver_net_amount` | `5310000` |
| `quote_version` | `1` |
| `currency` | `IRR` |

**Calculation:** 450 × 12,000 + 1 × 500,000 = 5,900,000 gross; 10% commission = 590,000.

---

## Step 2 — Return cached quote (same inputs)

Run the **same** request again (same `shipment_id`, same body, `force_recalculate: false`).

**Expected:** `200 OK`, same `quote_id` as Step 1.

---

## Step 3 — Force recalculate (new version)

Same `shipment_id`, change body:

```json
{
  "inputs": {
    "distance_km": 450,
    "stop_count": 2,
    "cargo_type": "general",
    "vehicle_type": "trailer"
  },
  "force_recalculate": true
}
```

**Expected:** `201 Created`, `quote_version` = `2`, new `quote_id`.

---

## Step 4 — Get latest quote

**Endpoint:** `GET /api/v1/pricing/shipments/{shipment_id}/quotes/latest`

1. Set `shipment_id` = `shp-swagger-001`
2. **Execute**

**Expected:** `200 OK`, matches the latest quote (version 2 after Step 3).

---

## Step 5 — Confirm snapshot

**Endpoint:** `POST /api/v1/pricing/shipments/{shipment_id}/confirm-snapshot`

Swagger does not always show custom headers in the main form. Use one of these:

### Option A — Authorize / headers (if available)

Add header:

| Header | Value |
|--------|-------|
| `Idempotency-Key` | `swagger-idem-001` |

Optional:

| Header | Value |
|--------|-------|
| `X-Correlation-Id` | `my-test-run-1` |

### Option B — curl from Swagger’s curl snippet

After **Try it out**, add the header in the generated curl or use:

```bash
curl -X POST "http://localhost:8000/api/v1/pricing/shipments/shp-swagger-001/confirm-snapshot" \
  -H "Idempotency-Key: swagger-idem-001" \
  -H "X-Correlation-Id: my-test-run-1"
```

**Expected:** `201 Created` with `snapshot_id`, amounts frozen from latest quote.

---

## Step 6 — Idempotent replay

Repeat Step 5 with the **same** `Idempotency-Key`.

**Expected:** `200 OK`, same `snapshot_id`, no second snapshot in DB.

---

## Step 7 — Get snapshot

**Endpoint:** `GET /api/v1/pricing/shipments/{shipment_id}/snapshot`

**Expected:** `200 OK`, same snapshot as Step 5.

---

## Error scenarios to try

### Unknown rate card → 422

```json
{
  "inputs": {
    "distance_km": 100,
    "stop_count": 1,
    "cargo_type": "hazmat",
    "vehicle_type": "trailer"
  },
  "force_recalculate": false
}
```

**Expected:** `422`, `"code": "UNKNOWN_RATE_CARD"`

### Invalid distance → 422

Set `"distance_km": 0` → **Expected:** `422`, `"code": "VALIDATION_ERROR"`

### Confirm without quote → 404

Use a new `shipment_id` (e.g. `shp-no-quote`) with **confirm-snapshot** and any `Idempotency-Key`.

**Expected:** `404`, `"code": "QUOTE_NOT_FOUND"`

### Second confirm, different key → 409

On a shipment that already has a snapshot, confirm again with a **new** `Idempotency-Key`.

**Expected:** `409`, `"code": "SNAPSHOT_ALREADY_EXISTS"`

### Same key, different shipment → 409

1. Quote + confirm `shp-a` with `Idempotency-Key: shared-key`
2. Quote + confirm `shp-b` with the same `Idempotency-Key: shared-key`

**Expected on step 2:** `409`, `"code": "IDEMPOTENCY_CONFLICT"`

### Get snapshot when none exists → 404

**GET** snapshot for `shp-no-quote` → `404`, `"code": "SNAPSHOT_NOT_FOUND"`

---

## Verify Redis event (optional)

After first confirm (Step 5), check the event stream:

```bash
docker compose exec redis redis-cli XRANGE asanbar:events - +
```

**Expected:** one entry with `"event_type":"price_snapshot.created"` and matching amounts.

Replay (Step 6) should **not** add a second entry.

---

## Rate card reference

| cargo_type | vehicle_type | rate/km (IRR) | stop fee (IRR) |
|------------|--------------|---------------|----------------|
| general | trailer | 12,000 | 500,000 |
| general | single | 10,000 | 400,000 |
| refrigerated | trailer | 15,000 | 600,000 |

Commission: 10% (`commission_rate_bps = 1000`).

---

## Troubleshooting

| Problem | What to check |
|---------|----------------|
| Swagger page won’t load | Is uvicorn running? Correct port? |
| `/ready` → 503 | `docker compose ps`, Postgres on 5432, `DATABASE_URL` |
| Confirm fails (missing header) | `Idempotency-Key` is required |
| All amounts zero / wrong | Rate card seed: run `alembic upgrade head` |
| Redis event missing | `docker compose ps` redis; confirm was first success (not replay) |

---

## Quick checklist

- [ ] `/health` and `/ready` return 200
- [ ] Quote returns expected amounts for 450 km / 2 stops / general + trailer
- [ ] Same inputs return cached quote (200)
- [ ] `force_recalculate: true` bumps version
- [ ] Confirm with `Idempotency-Key` returns 201
- [ ] Replay returns 200, same snapshot
- [ ] GET snapshot returns frozen prices
- [ ] Error cases return correct codes (422, 404, 409)
