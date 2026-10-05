import pytest
from httpx import AsyncClient

QUOTE_URL = "/api/v1/pricing/shipments/{shipment_id}/quote"
LATEST_URL = "/api/v1/pricing/shipments/{shipment_id}/quotes/latest"

SPEC_BODY = {
    "inputs": {
        "distance_km": 450,
        "stop_count": 2,
        "cargo_type": "general",
        "vehicle_type": "trailer",
    },
    "force_recalculate": False,
}


@pytest.mark.asyncio
async def test_quote_example_from_spec(client: AsyncClient) -> None:
    response = await client.post(QUOTE_URL.format(shipment_id="shp-001"), json=SPEC_BODY)
    assert response.status_code == 201
    data = response.json()
    assert data["gross_amount"] == 5_900_000
    assert data["commission_amount"] == 590_000
    assert data["driver_net_amount"] == 5_310_000
    assert data["currency"] == "IRR"
    assert data["breakdown"]["distance_amount"] == 5_400_000
    assert data["breakdown"]["stop_fee"] == 500_000
    assert data["quote_version"] == 1


@pytest.mark.asyncio
async def test_unknown_rate_card_returns_422(client: AsyncClient) -> None:
    body = {
        "inputs": {
            "distance_km": 100,
            "stop_count": 1,
            "cargo_type": "hazmat",
            "vehicle_type": "trailer",
        },
        "force_recalculate": False,
    }
    response = await client.post(
        QUOTE_URL.format(shipment_id="shp-002"),
        json=body,
        headers={"X-Correlation-Id": "req-xyz"},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "UNKNOWN_RATE_CARD"
    assert error["correlation_id"] == "req-xyz"


@pytest.mark.asyncio
async def test_same_inputs_return_same_quote_id(client: AsyncClient) -> None:
    shipment_id = "shp-reuse"
    first = await client.post(QUOTE_URL.format(shipment_id=shipment_id), json=SPEC_BODY)
    second = await client.post(QUOTE_URL.format(shipment_id=shipment_id), json=SPEC_BODY)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["quote_id"] == second.json()["quote_id"]
    assert second.json()["quote_version"] == 1


@pytest.mark.asyncio
async def test_force_recalculate_bumps_version(client: AsyncClient) -> None:
    shipment_id = "shp-recalc"
    first = await client.post(QUOTE_URL.format(shipment_id=shipment_id), json=SPEC_BODY)
    assert first.status_code == 201
    assert first.json()["quote_version"] == 1

    recalc_body = {**SPEC_BODY, "force_recalculate": True}
    second = await client.post(QUOTE_URL.format(shipment_id=shipment_id), json=recalc_body)
    assert second.status_code == 201
    assert second.json()["quote_version"] == 2
    assert second.json()["quote_id"] != first.json()["quote_id"]


@pytest.mark.asyncio
async def test_get_latest_quote(client: AsyncClient) -> None:
    shipment_id = "shp-latest"
    created = await client.post(QUOTE_URL.format(shipment_id=shipment_id), json=SPEC_BODY)
    assert created.status_code == 201

    latest = await client.get(LATEST_URL.format(shipment_id=shipment_id))
    assert latest.status_code == 200
    assert latest.json()["quote_id"] == created.json()["quote_id"]


@pytest.mark.asyncio
async def test_get_latest_quote_not_found(client: AsyncClient) -> None:
    response = await client.get(LATEST_URL.format(shipment_id="shp-missing"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUOTE_NOT_FOUND"


@pytest.mark.asyncio
async def test_invalid_distance_returns_validation_error(client: AsyncClient) -> None:
    body = {
        "inputs": {
            "distance_km": 0,
            "stop_count": 1,
            "cargo_type": "general",
            "vehicle_type": "trailer",
        },
        "force_recalculate": False,
    }
    response = await client.post(QUOTE_URL.format(shipment_id="shp-invalid"), json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
