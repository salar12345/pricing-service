from redis.asyncio import Redis

from app.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


async def init_redis(redis_url: str | None = None) -> Redis:
    global _redis
    if _redis is not None:
        await close_redis()
    url = redis_url or get_settings().redis_url
    _redis = Redis.from_url(url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except RuntimeError:
            pass
        _redis = None
