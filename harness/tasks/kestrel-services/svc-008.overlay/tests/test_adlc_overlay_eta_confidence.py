"""ADLC harness overlay for svc-008: ShipmentOut must carry an optional eta_confidence in 0..1."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gateway.models import ShipmentOut
from tests.conftest import BOOKING, SHIPMENT, json_response


def test_model_passes_eta_confidence_through():
    out = ShipmentOut.model_validate({**SHIPMENT, "eta_confidence": 0.82})

    assert out.eta_confidence == 0.82
    assert out.model_dump(mode="json")["eta_confidence"] == 0.82


def test_model_defaults_to_none_when_booking_omits_it():
    out = ShipmentOut.model_validate(SHIPMENT)

    assert out.eta_confidence is None


def test_model_accepts_explicit_null_and_the_bounds():
    assert ShipmentOut.model_validate({**SHIPMENT, "eta_confidence": None}).eta_confidence is None
    assert ShipmentOut.model_validate({**SHIPMENT, "eta_confidence": 0}).eta_confidence == 0
    assert ShipmentOut.model_validate({**SHIPMENT, "eta_confidence": 1}).eta_confidence == 1


@pytest.mark.parametrize("value", [-0.01, 1.01, 5])
def test_model_rejects_values_outside_zero_to_one(value):
    with pytest.raises(ValidationError):
        ShipmentOut.model_validate({**SHIPMENT, "eta_confidence": value})


def test_field_is_optional_in_the_schema():
    field = ShipmentOut.model_fields["eta_confidence"]

    assert not field.is_required()


def test_route_returns_eta_confidence_when_booking_sends_it(client, upstream):
    upstream.get(f"{BOOKING}/v2/shipments/41").mock(
        return_value=json_response({**SHIPMENT, "eta_confidence": 0.75})
    )

    body = client.get("/api/shipments/41").json()

    assert body["eta_confidence"] == 0.75


def test_route_still_works_when_booking_omits_it(client, upstream):
    upstream.get(f"{BOOKING}/v2/shipments/41").mock(return_value=json_response(SHIPMENT))

    resp = client.get("/api/shipments/41")

    assert resp.status_code == 200
    assert resp.json().get("eta_confidence") is None
