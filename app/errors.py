from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class UnknownRateCardError(AppError):
    def __init__(self, cargo_type: str, vehicle_type: str) -> None:
        super().__init__(
            code="UNKNOWN_RATE_CARD",
            message=f"No rate card for cargo_type={cargo_type}, vehicle_type={vehicle_type}",
            status_code=422,
        )


class QuoteNotFoundError(AppError):
    def __init__(self, shipment_id: str) -> None:
        super().__init__(
            code="QUOTE_NOT_FOUND",
            message=f"No quote found for shipment {shipment_id}",
            status_code=404,
        )


class SnapshotNotFoundError(AppError):
    def __init__(self, shipment_id: str) -> None:
        super().__init__(
            code="SNAPSHOT_NOT_FOUND",
            message=f"No snapshot found for shipment {shipment_id}",
            status_code=404,
        )


class SnapshotAlreadyExistsError(AppError):
    def __init__(self, shipment_id: str) -> None:
        super().__init__(
            code="SNAPSHOT_ALREADY_EXISTS",
            message=f"Snapshot already confirmed for shipment {shipment_id}",
            status_code=409,
        )


class IdempotencyConflictError(AppError):
    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            code="IDEMPOTENCY_CONFLICT",
            message=f"Idempotency key {idempotency_key} was already used for a different shipment",
            status_code=409,
        )


def _error_body(code: str, message: str, correlation_id: str | None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": correlation_id,
        }
    }


def _correlation_id_from_request(request: Request) -> str | None:
    return request.headers.get("X-Correlation-Id")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, _correlation_id_from_request(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        messages = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        return JSONResponse(
            status_code=422,
            content=_error_body("VALIDATION_ERROR", messages, _correlation_id_from_request(request)),
        )
