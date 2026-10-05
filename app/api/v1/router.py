from fastapi import APIRouter

from app.api.v1 import pricing

router = APIRouter(prefix="/api/v1")
router.include_router(pricing.router)
