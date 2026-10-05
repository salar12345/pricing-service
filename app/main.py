from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.api.deps import reset_event_publisher
from app.config import get_settings
from app.db import check_database_connection, get_engine
from app.errors import register_exception_handlers
from app.redis_client import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    get_engine()
    await init_redis(settings.redis_url)
    yield
    reset_event_publisher()
    await close_redis()
    await get_engine().dispose()


app = FastAPI(title="Pricing Service", version="0.1.0", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    if await check_database_connection():
        return JSONResponse(content={"status": "ready"})
    return JSONResponse(status_code=503, content={"status": "not_ready"})


@app.get("/")
async def root() -> dict[str, str]:
    settings = get_settings()
    return {"service": "pricing-service", "log_level": settings.log_level}
