"""HTTP client for querying real-time ISS orbital telemetry."""

from __future__ import annotations

import logging
from typing import Any, Self

import httpx

from space_suite.iss.models import ISSTelemetry

logger = logging.getLogger(__name__)

DEFAULT_API_URL: str = "https://api.wheretheiss.at/v1/satellites/25544"
DEFAULT_TIMEOUT_SECONDS: float = 6.0


class TelemetryError(Exception):
    """Raised when ISS telemetry cannot be retrieved or parsed."""


class ISSClient:
    """Client for fetching live telemetry from WhereTheISS.at."""

    def __init__(
        self,
        endpoint_url: str = DEFAULT_API_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.timeout = timeout
        self._external_client = client is not None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "SpaceSuite-ISSTracker/1.0"},
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close underlying HTTP client if owned."""
        if not self._external_client:
            self._client.close()

    def fetch_telemetry(self) -> ISSTelemetry:
        """Query the API and return a parsed ISSTelemetry object."""
        try:
            response = self._client.get(self.endpoint_url)
            response.raise_for_status()
            data = response.json()
            return self._parse_payload(data)
        except httpx.HTTPStatusError as err:
            logger.error("HTTP error %s querying ISS telemetry", err.response.status_code)
            raise TelemetryError(
                f"API returned HTTP {err.response.status_code}: {err.response.text}"
            ) from err
        except httpx.RequestError as err:
            logger.error("Network error querying ISS API: %s", err)
            raise TelemetryError(f"Network error communicating with ISS API: {err}") from err
        except (KeyError, ValueError, TypeError) as err:
            logger.error("Failed to parse ISS telemetry payload: %s", err)
            raise TelemetryError(f"Malformed ISS API payload: {err}") from err

    @staticmethod
    def _parse_payload(data: dict[str, Any]) -> ISSTelemetry:
        """Validate and parse raw JSON into ISSTelemetry."""
        return ISSTelemetry(
            name=str(data.get("name", "iss")),
            id=int(data["id"]),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            altitude_km=float(data["altitude"]),
            velocity_kmh=float(data["velocity"]),
            visibility=str(data.get("visibility", "unknown")),
            footprint_km=float(data.get("footprint", 0.0)),
            timestamp=float(data["timestamp"]),
            solar_lat=float(data.get("solar_lat", 0.0)),
            solar_lon=float(data.get("solar_lon", 0.0)),
        )
