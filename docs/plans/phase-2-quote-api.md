# Phase 2 — Domain & Quote API

## Status

done

## Goal

Implement pricing calculation, quote persistence, and POST/GET quote endpoints.

## Scope

- Pure domain math in `app/domain/pricing.py`
- Repositories: rate_card, commission, quote
- `QuoteService` with reuse and version bump
- Error envelope + correlation ID
- Unit and integration tests

## Test plan

- [x] Unit: commission math + money invariant
- [x] Integration: spec example (450 km → 5_900_000 gross)
- [x] Integration: unknown rate card → 422 `UNKNOWN_RATE_CARD`
- [x] Integration: same inputs → same `quote_id`
- [x] Integration: `force_recalculate` bumps version
- [x] Integration: GET latest quote / 404

## Files added

- `app/domain/pricing.py`
- `app/errors.py`
- `app/schemas/quote.py`
- `app/repositories/{rate_card,commission,quote}.py`
- `app/services/quote_service.py`
- `app/api/deps.py`, `app/api/v1/{router,pricing}.py`
- `tests/unit/test_pricing_math.py`
- `tests/integration/test_quote_api.py`
