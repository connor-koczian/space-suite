"""ISS tracking data models and coordinate structures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ObserverCoords:
    """Ground station or observer coordinates."""

    latitude: float
    longitude: float
    altitude_km: float = 0.0
    name: str = "Ground Station"

    def __post_init__(self) -> None:
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError(f"Latitude must be in [-90, 90], got {self.latitude}")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError(f"Longitude must be in [-180, 180], got {self.longitude}")

    @property
    def lat_str(self) -> str:
        hemi = "N" if self.latitude >= 0 else "S"
        return f"{abs(self.latitude):.4f}° {hemi}"

    @property
    def lon_str(self) -> str:
        hemi = "E" if self.longitude >= 0 else "W"
        return f"{abs(self.longitude):.4f}° {hemi}"


@dataclass(frozen=True)
class ISSTelemetry:
    """Instantaneous orbital telemetry of the International Space Station."""

    name: str
    id: int
    latitude: float
    longitude: float
    altitude_km: float
    velocity_kmh: float
    visibility: str
    footprint_km: float
    timestamp: float
    solar_lat: float = 0.0
    solar_lon: float = 0.0

    @property
    def velocity_kms(self) -> float:
        """Velocity in kilometers per second."""
        return self.velocity_kmh / 3600.0

    @property
    def lat_str(self) -> str:
        hemi = "N" if self.latitude >= 0 else "S"
        return f"{abs(self.latitude):.4f}° {hemi}"

    @property
    def lon_str(self) -> str:
        hemi = "E" if self.longitude >= 0 else "W"
        return f"{abs(self.longitude):.4f}° {hemi}"

    @property
    def time_utc(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp, tz=UTC)

    @property
    def is_sunlit(self) -> bool:
        return self.visibility.lower() == "daylight"


@dataclass
class RelativePosition:
    """Relative geometry between observer and the ISS."""

    ground_distance_km: float
    slant_range_km: float
    elevation_deg: float
    bearing_deg: float
    compass_heading: str
    is_above_horizon: bool
    is_in_range: bool

    @property
    def ground_distance_miles(self) -> float:
        return self.ground_distance_km * 0.621371

    @property
    def slant_range_miles(self) -> float:
        return self.slant_range_km * 0.621371
