from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.pricing import calculate_quote
from app.errors import QuoteNotFoundError, UnknownRateCardError
from app.models.quote import PricingQuote
from app.repositories import commission as commission_repo
from app.repositories import quote as quote_repo
from app.repositories import rate_card as rate_card_repo
from app.schemas.quote import QuoteBreakdownResponse, QuoteRequest, QuoteResponse, ShipmentInputs


def _breakdown_to_dict(breakdown: QuoteBreakdownResponse) -> dict:
    return breakdown.model_dump()


def _quote_to_response(quote: PricingQuote) -> QuoteResponse:
    breakdown = quote.breakdown
    return QuoteResponse(
        quote_id=str(quote.id),
        shipment_id=quote.shipment_id,
        quote_version=quote.quote_version,
        inputs=ShipmentInputs(
            distance_km=quote.distance_km,
            stop_count=quote.stop_count,
            cargo_type=quote.cargo_type,
            vehicle_type=quote.vehicle_type,
        ),
        gross_amount=quote.gross_amount,
        commission_amount=quote.commission_amount,
        driver_net_amount=quote.driver_net_amount,
        breakdown=QuoteBreakdownResponse(**breakdown),
        created_at=quote.created_at,
    )


class QuoteService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_or_get_quote(
        self, shipment_id: str, request: QuoteRequest
    ) -> tuple[QuoteResponse, bool]:
        inputs = request.inputs

        if not request.force_recalculate:
            existing = await quote_repo.find_matching_quote(self._session, shipment_id, inputs)
            if existing is not None:
                return _quote_to_response(existing), False

        rate_card = await rate_card_repo.get_rate_card(
            self._session, inputs.cargo_type, inputs.vehicle_type
        )
        if rate_card is None:
            raise UnknownRateCardError(inputs.cargo_type, inputs.vehicle_type)

        commission_rule = await commission_repo.get_active_commission_rule(self._session)
        if commission_rule is None:
            raise UnknownRateCardError(inputs.cargo_type, inputs.vehicle_type)

        amounts = calculate_quote(
            distance_km=inputs.distance_km,
            stop_count=inputs.stop_count,
            rate_per_km=rate_card.rate_per_km,
            stop_fee_per_stop=rate_card.stop_fee,
            commission_rate_bps=commission_rule.commission_rate_bps,
        )

        next_version = await quote_repo.get_max_quote_version(self._session, shipment_id) + 1
        breakdown = QuoteBreakdownResponse(**asdict(amounts.breakdown))

        quote = await quote_repo.create_quote(
            self._session,
            shipment_id=shipment_id,
            quote_version=next_version,
            inputs=inputs,
            gross_amount=amounts.gross_amount,
            commission_amount=amounts.commission_amount,
            driver_net_amount=amounts.driver_net_amount,
            breakdown=_breakdown_to_dict(breakdown),
        )
        await self._session.commit()
        return _quote_to_response(quote), True

    async def get_latest_quote(self, shipment_id: str) -> QuoteResponse:
        quote = await quote_repo.get_latest_quote(self._session, shipment_id)
        if quote is None:
            raise QuoteNotFoundError(shipment_id)
        return _quote_to_response(quote)
