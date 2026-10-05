from app.domain.pricing import calculate_quote


def test_commission_math_spec_example() -> None:
    amounts = calculate_quote(
        distance_km=450,
        stop_count=2,
        rate_per_km=12_000,
        stop_fee_per_stop=500_000,
        commission_rate_bps=1000,
    )
    assert amounts.gross_amount == 5_900_000
    assert amounts.commission_amount == 590_000
    assert amounts.driver_net_amount == 5_310_000
    assert amounts.driver_net_amount + amounts.commission_amount == amounts.gross_amount


def test_money_invariant() -> None:
    amounts = calculate_quote(
        distance_km=123,
        stop_count=3,
        rate_per_km=10_000,
        stop_fee_per_stop=400_000,
        commission_rate_bps=1000,
    )
    assert amounts.driver_net_amount + amounts.commission_amount == amounts.gross_amount
    assert all(
        isinstance(v, int)
        for v in (
            amounts.gross_amount,
            amounts.commission_amount,
            amounts.driver_net_amount,
        )
    )


def test_commission_rounding() -> None:
    amounts = calculate_quote(
        distance_km=1,
        stop_count=1,
        rate_per_km=333,
        stop_fee_per_stop=0,
        commission_rate_bps=1000,
    )
    assert amounts.gross_amount == 333
    assert amounts.commission_amount == round(333 * 1000 / 10_000)
    assert amounts.driver_net_amount + amounts.commission_amount == amounts.gross_amount


def test_single_stop_has_no_stop_fee() -> None:
    amounts = calculate_quote(
        distance_km=100,
        stop_count=1,
        rate_per_km=12_000,
        stop_fee_per_stop=500_000,
        commission_rate_bps=1000,
    )
    assert amounts.breakdown.stop_fee == 0
    assert amounts.gross_amount == 1_200_000

