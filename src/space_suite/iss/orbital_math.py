"""Orbital and spherical geometry calculations for satellite tracking."""

from __future__ import annotations

import math
from collections.abc import Sequence

from space_suite.iss.models import ISSTelemetry, ObserverCoords, RelativePosition

EARTH_RADIUS_KM: float = 6371.0

CARDINAL_DIRECTIONS: Sequence[str] = (
    "N", "NNE", "NE", "ENE",
    "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW",
    "W", "WNW", "NW", "NNW",
)


def central_angle(lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float) -> float:
    """Compute central angle (in radians) between two geographic coordinates on Earth.
    
    Uses Haversine formula for numerical stability at small distances.
    """
    phi1 = math.radians(lat1_deg)
    phi2 = math.radians(lat2_deg)
    delta_phi = math.radians(lat2_deg - lat1_deg)
    delta_lambda = math.radians(lon2_deg - lon1_deg)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    # Clamp to prevent float precision overshoot outside [0, 1]
    a_clamped = min(1.0, max(0.0, a))
    return 2.0 * math.asin(math.sqrt(a_clamped))


def haversine_distance(
    lat1_deg: float,
    lon1_deg: float,
    lat2_deg: float,
    lon2_deg: float,
    radius_km: float = EARTH_RADIUS_KM,
) -> float:
    """Great-circle surface distance in kilometers."""
    return radius_km * central_angle(lat1_deg, lon1_deg, lat2_deg, lon2_deg)


def slant_range(
    lat1_deg: float,
    lon1_deg: float,
    alt1_km: float,
    lat2_deg: float,
    lon2_deg: float,
    alt2_km: float,
    radius_km: float = EARTH_RADIUS_KM,
) -> float:
    """Direct 3D Euclidean distance (line-of-sight slant range) in kilometers.
    
    Derived from spherical law of cosines on the Earth-center triangle:
      r1 = radius + alt1
      r2 = radius + alt2
      d^2 = r1^2 + r2^2 - 2*r1*r2*cos(theta)
    """
    theta = central_angle(lat1_deg, lon1_deg, lat2_deg, lon2_deg)
    r1 = radius_km + alt1_km
    r2 = radius_km + alt2_km
    d_sq = r1 * r1 + r2 * r2 - 2.0 * r1 * r2 * math.cos(theta)
    return math.sqrt(max(0.0, d_sq))


def elevation_angle(
    lat1_deg: float,
    lon1_deg: float,
    alt1_km: float,
    lat2_deg: float,
    lon2_deg: float,
    alt2_km: float,
    radius_km: float = EARTH_RADIUS_KM,
) -> float:
    """Calculate the satellite's elevation angle (degrees above the observer's horizon).
    
    Returns:
        Degrees in range [-90.0, 90.0].
        Positive values (> 0°) mean the satellite is above the horizon (line of sight).
        Negative values mean the satellite is below the horizon blocked by Earth's curvature.
        90° means directly overhead at the zenith.
    """
    theta = central_angle(lat1_deg, lon1_deg, lat2_deg, lon2_deg)
    r1 = radius_km + alt1_km
    r2 = radius_km + alt2_km
    d_slant = slant_range(lat1_deg, lon1_deg, alt1_km, lat2_deg, lon2_deg, alt2_km, radius_km)

    if d_slant < 1e-6:
        return 90.0

    # Sine of elevation angle: (r2 * cos(theta) - r1) / d_slant
    sin_el = (r2 * math.cos(theta) - r1) / d_slant
    sin_el_clamped = min(1.0, max(-1.0, sin_el))
    return math.degrees(math.asin(sin_el_clamped))


def compass_bearing(lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float) -> float:
    """Initial forward compass azimuth from point 1 to point 2 (degrees 0 to 360)."""
    phi1 = math.radians(lat1_deg)
    phi2 = math.radians(lat2_deg)
    delta_lambda = math.radians(lon2_deg - lon1_deg)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

    bearing_deg = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return bearing_deg


def degrees_to_cardinal(bearing_deg: float) -> str:
    """Convert azimuth degrees [0, 360) to 16-point cardinal string (e.g. 'NNW')."""
    idx = int((bearing_deg + 11.25) / 22.5) % 16
    return CARDINAL_DIRECTIONS[idx]


def compute_relative_position(
    obs: ObserverCoords,
    iss: ISSTelemetry,
    threshold_km: float = 1000.0,
    min_elevation_deg: float = 0.0,
) -> RelativePosition:
    """Compute complete relative geometry and status between observer and ISS."""
    g_dist = haversine_distance(obs.latitude, obs.longitude, iss.latitude, iss.longitude)
    s_range = slant_range(
        obs.latitude,
        obs.longitude,
        obs.altitude_km,
        iss.latitude,
        iss.longitude,
        iss.altitude_km,
    )
    el = elevation_angle(
        obs.latitude,
        obs.longitude,
        obs.altitude_km,
        iss.latitude,
        iss.longitude,
        iss.altitude_km,
    )
    bearing = compass_bearing(obs.latitude, obs.longitude, iss.latitude, iss.longitude)
    cardinal = degrees_to_cardinal(bearing)

    above_horizon = el > min_elevation_deg
    in_range = (g_dist <= threshold_km) or (above_horizon and el >= 10.0)

    return RelativePosition(
        ground_distance_km=g_dist,
        slant_range_km=s_range,
        elevation_deg=el,
        bearing_deg=bearing,
        compass_heading=cardinal,
        is_above_horizon=above_horizon,
        is_in_range=in_range,
    )


EARTH_MU_KM3_S2: float = 398600.4418  # Standard gravitational parameter GM in km^3/s^2


def calculate_orbital_period_seconds(
    altitude_km: float,
    radius_km: float = EARTH_RADIUS_KM,
    mu_km3_s2: float = EARTH_MU_KM3_S2,
) -> float:
    """Compute circular orbital period in seconds using Kepler's 3rd law: T = 2*pi*sqrt(a^3 / mu)."""
    semi_major_axis = radius_km + altitude_km
    return 2.0 * math.pi * math.sqrt((semi_major_axis**3) / mu_km3_s2)


def calculate_orbital_period_minutes(
    altitude_km: float,
    radius_km: float = EARTH_RADIUS_KM,
    mu_km3_s2: float = EARTH_MU_KM3_S2,
) -> float:
    """Orbital period in minutes."""
    return calculate_orbital_period_seconds(altitude_km, radius_km, mu_km3_s2) / 60.0
