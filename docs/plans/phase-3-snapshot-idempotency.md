# Phase 3 — Snapshot & Idempotency

## Status

done

## Goal

Freeze latest quote as immutable snapshot on confirm; handle idempotency correctly.

## Decision tree (confirm-snapshot)

1. Missing `Idempotency-Key` → 422
2. Key exists for this shipment → 200, same snapshot, no event
3. Key exists for different shipment → 409 `IDEMPOTENCY_CONFLICT`
4. Snapshot already exists → 409 `SNAPSHOT_ALREADY_EXISTS`
5. No quote → 404 `QUOTE_NOT_FOUND`
6. First success → 201, snapshot + idempotency record + event publisher call

## Test plan

- [x] Confirm twice same key → one snapshot, publisher called once
- [x] Second confirm different key → 409 `SNAPSHOT_ALREADY_EXISTS`
- [x] Confirm without quote → 404
- [x] Same key different shipment → 409 `IDEMPOTENCY_CONFLICT`
- [x] GET snapshot / 404

## Files added

- `app/schemas/snapshot.py`
- `app/repositories/{snapshot,idempotency}.py`
- `app/services/snapshot_service.py`
- `app/events/publisher.py` (NoOp stub; Redis in Phase 4)
- `tests/integration/test_snapshot_api.py`
