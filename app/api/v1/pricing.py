from fastapi import APIRouter, Depends, Header, Response, status

from app.api.deps import get_correlation_id, get_quote_service, get_snapshot_service
from app.schemas.quote import QuoteRequest, QuoteResponse
from app.schemas.snapshot import SnapshotResponse
from app.services.quote_service import QuoteService
from app.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.post(
    "/shipments/{shipment_id}/quote",
    response_model=QuoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_quote(
    shipment_id: str,
    body: QuoteRequest,
    response: Response,
    service: QuoteService = Depends(get_quote_service),
) -> QuoteResponse:
    quote, created = await service.create_or_get_quote(shipment_id, body)
    if not created:
        response.status_code = status.HTTP_200_OK
    return quote


@router.get(
    "/shipments/{shipment_id}/quotes/latest",
    response_model=QuoteResponse,
)
async def get_latest_quote(
    shipment_id: str,
    service: QuoteService = Depends(get_quote_service),
) -> QuoteResponse:
    return await service.get_latest_quote(shipment_id)


@router.post(
    "/shipments/{shipment_id}/confirm-snapshot",
    response_model=SnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_snapshot(
    shipment_id: str,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    correlation_id: str | None = Depends(get_correlation_id),
    service: SnapshotService = Depends(get_snapshot_service),
) -> SnapshotResponse:
    snapshot, created = await service.confirm_snapshot(
        shipment_id, idempotency_key, correlation_id
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return snapshot


@router.get(
    "/shipments/{shipment_id}/snapshot",
    response_model=SnapshotResponse,
)
async def get_snapshot(
    shipment_id: str,
    service: SnapshotService = Depends(get_snapshot_service),
) -> SnapshotResponse:
    return await service.get_snapshot(shipment_id)
