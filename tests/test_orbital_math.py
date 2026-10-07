"""Unit tests for orbital mechanics and spherical coordinate mathematics."""

import math

import pytest

from space_suite.iss.models import ISSTelemetry, ObserverCoords
from space_suite.iss.orbital_math import (
    EARTH_RADIUS_KM,
    compass_bearing,
    compute_relative_position,
    degrees_to_cardinal,
    elevation_angle,
    haversine_distance,
    slant_range,
)


def test_haversine_zero_distance():
    lat, lon = 51.5074, -0.1278
    dist = haversine_distance(lat, lon, lat, lon)
    assert dist == pytest.approx(0.0, abs=1e-5)


def test_haversine_london_to_paris():
    # London: 51.5074° N, 0.1278° W
    # Paris: 48.8566° N, 2.3522° E
    # Expected great-circle distance is approx 343 km
    dist = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)
    assert 340.0 < dist < 350.0


def test_haversine_antipodal():
    # Antipodal distance: from (0, 0) to (0, 180) is half circumference
    dist = haversine_distance(0.0, 0.0, 0.0, 180.0)
    expected = math.pi * EARTH_RADIUS_KM
    assert dist == pytest.approx(expected, rel=1e-3)


def test_slant_range_zenith():
    # Directly overhead: distance should equal altitude difference
    lat, lon = 25.0, 45.0
    s_range = slant_range(lat, lon, 0.0, lat, lon, 420.0)
    assert s_range == pytest.approx(420.0, abs=1e-4)


def test_slant_range_antipodal():
    # Antipodal: observer at (0, 0), satellite at (0, 180, 420)
    s_range = slant_range(0.0, 0.0, 0.0, 0.0, 180.0, 420.0)
    expected = EARTH_RADIUS_KM + (EARTH_RADIUS_KM + 420.0)
    assert s_range == pytest.approx(expected, abs=1e-3)


def test_elevation_angle_zenith():
    # Directly overhead should be exactly 90 degrees
    el = elevation_angle(10.0, 20.0, 0.0, 10.0, 20.0, 420.0)
    assert el == pytest.approx(90.0, abs=1e-4)


def test_elevation_angle_geometric_horizon():
    # Satellite at geometric horizon where cos(theta) = r1 / r2
    r1 = EARTH_RADIUS_KM
    r2 = EARTH_RADIUS_KM + 420.0
    theta_rad = math.acos(r1 / r2)
    delta_lat_deg = math.degrees(theta_rad)

    el = elevation_angle(0.0, 0.0, 0.0, delta_lat_deg, 0.0, 420.0)
    assert el == pytest.approx(0.0, abs=1e-3)


def test_elevation_angle_below_horizon():
    # Quarter around the globe: should be well below horizon (negative elevation)
    el = elevation_angle(0.0, 0.0, 0.0, 90.0, 0.0, 420.0)
    assert el < -30.0


def test_compass_bearing_cardinals():
    # North
    assert compass_bearing(0.0, 0.0, 10.0, 0.0) == pytest.approx(0.0, abs=1e-4)
    # East
    assert compass_bearing(0.0, 0.0, 0.0, 10.0) == pytest.approx(90.0, abs=1e-4)
    # South
    assert compass_bearing(10.0, 0.0, 0.0, 0.0) == pytest.approx(180.0, abs=1e-4)
    # West
    assert compass_bearing(0.0, 10.0, 0.0, 0.0) == pytest.approx(270.0, abs=1e-4)


def test_degrees_to_cardinal():
    assert degrees_to_cardinal(0.0) == "N"
    assert degrees_to_cardinal(45.0) == "NE"
    assert degrees_to_cardinal(90.0) == "E"
    assert degrees_to_cardinal(135.0) == "SE"
    assert degrees_to_cardinal(180.0) == "S"
    assert degrees_to_cardinal(225.0) == "SW"
    assert degrees_to_cardinal(270.0) == "W"
    assert degrees_to_cardinal(315.0) == "NW"


def test_compute_relative_position():
    obs = ObserverCoords(latitude=51.5074, longitude=-0.1278, altitude_km=0.0, name="London")
    iss = ISSTelemetry(
        name="iss",
        id=25544,
        latitude=51.5074,
        longitude=-0.1278,
        altitude_km=420.0,
        velocity_kmh=27600.0,
        visibility="daylight",
        footprint_km=4500.0,
        timestamp=1700000000.0,
    )

    rel = compute_relative_position(obs, iss, threshold_km=500.0)
    assert rel.ground_distance_km == pytest.approx(0.0, abs=1e-4)
    assert rel.slant_range_km == pytest.approx(420.0, abs=1e-4)
    assert rel.elevation_deg == pytest.approx(90.0, abs=1e-4)
    assert rel.is_above_horizon is True
    assert rel.is_in_range is True


def test_calculate_orbital_period():
    from space_suite.iss.orbital_math import (
        calculate_orbital_period_minutes,
        calculate_orbital_period_seconds,
    )

    # At 425 km circular orbit, orbital period should be approx 93 minutes (~5580 seconds)
    period_sec = calculate_orbital_period_seconds(425.0)
    period_min = calculate_orbital_period_minutes(425.0)

    assert 5500.0 < period_sec < 5650.0
    assert 92.0 < period_min < 94.0
    assert period_sec / 60.0 == pytest.approx(period_min, abs=1e-5)
