# Phase 4 — Redis Events

## Status

done

## Goal

Publish `price_snapshot.created` to Redis stream `asanbar:events` on first confirm only.

## Event format

- Stream: `asanbar:events`
- Field: `payload` (JSON) with `event_id`, `event_type`, `occurred_at`, `correlation_id`, `data`

## Test plan

- [x] First confirm → exactly one stream entry with correct payload
- [x] Idempotent replay → no additional stream entry
- [x] Payload matches spec fields and amounts

## Files added/updated

- `app/events/publisher.py` — `RedisEventPublisher`, `build_event_payload`
- `app/redis_client.py` — async Redis connection lifecycle
- `app/main.py` — init/close Redis on lifespan
- `tests/integration/test_redis_events.py`
- `tests/conftest.py` — fakeredis default for integration tests
