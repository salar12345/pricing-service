from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteBreakdown:
    base_amount: int
    distance_amount: int
    stop_fee: int
    rate_per_km: int
    commission_rate_bps: int


@dataclass(frozen=True)
class QuoteAmounts:
    gross_amount: int
    commission_amount: int
    driver_net_amount: int
    breakdown: QuoteBreakdown


def calculate_quote(
    distance_km: int,
    stop_count: int,
    rate_per_km: int,
    stop_fee_per_stop: int,
    commission_rate_bps: int,
) -> QuoteAmounts:
    distance_amount = distance_km * rate_per_km
    stop_fee_total = stop_fee_per_stop * max(0, stop_count - 1)
    gross = distance_amount + stop_fee_total
    commission = round(gross * commission_rate_bps / 10_000)
    driver_net = gross - commission

    if driver_net + commission != gross:
        raise ValueError("Money invariant violated: driver_net + commission != gross")

    breakdown = QuoteBreakdown(
        base_amount=gross,
        distance_amount=distance_amount,
        stop_fee=stop_fee_total,
        rate_per_km=rate_per_km,
        commission_rate_bps=commission_rate_bps,
    )
    return QuoteAmounts(
        gross_amount=gross,
        commission_amount=commission,
        driver_net_amount=driver_net,
        breakdown=breakdown,
    )
