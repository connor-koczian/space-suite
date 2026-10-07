"""Unit tests for ISS API client parsing and error handling."""

import pytest

from space_suite.iss.client import ISSClient


def test_parse_valid_payload():
    raw_payload = {
        "name": "iss",
        "id": 25544,
        "latitude": 42.1234,
        "longitude": -71.5678,
        "altitude": 418.5,
        "velocity": 27580.2,
        "visibility": "daylight",
        "footprint": 4502.1,
        "timestamp": 1700001234,
        "solar_lat": 12.5,
        "solar_lon": 85.0,
    }

    telemetry = ISSClient._parse_payload(raw_payload)
    assert telemetry.name == "iss"
    assert telemetry.id == 25544
    assert telemetry.latitude == 42.1234
    assert telemetry.longitude == -71.5678
    assert telemetry.altitude_km == 418.5
    assert telemetry.velocity_kmh == 27580.2
    assert telemetry.is_sunlit is True
    assert telemetry.velocity_kms == pytest.approx(27580.2 / 3600.0)


def test_parse_missing_required_field():
    raw_payload = {
        "name": "iss",
        "latitude": 42.1234,
        # missing id and altitude
    }
    with pytest.raises(KeyError):
        ISSClient._parse_payload(raw_payload)
