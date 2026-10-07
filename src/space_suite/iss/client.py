"""HTTP client for querying real-time ISS orbital telemetry with fallback redundancy."""

from __future__ import annotations

import logging
import time
from typing import Any, Self

import httpx

from space_suite.iss.models import ISSTelemetry

logger = logging.getLogger(__name__)

PRIMARY_API_URL: str = "https://api.wheretheiss.at/v1/satellites/25544"
FALLBACK_API_URL: str = "http://api.open-notify.org/iss-now.json"
DEFAULT_TIMEOUT_SECONDS: float = 6.0


class TelemetryError(Exception):
    """Raised when ISS telemetry cannot be retrieved or parsed."""


class ISSClient:
    """Client for fetching live telemetry with automatic keepalive-recovery and fallback redundancy."""

    def __init__(
        self,
        endpoint_url: str = PRIMARY_API_URL,
        fallback_url: str = FALLBACK_API_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.fallback_url = fallback_url
        self.timeout = timeout
        self._external_client = client is not None
        # Connection: close prevents stale keep-alive disconnects on Apache servers
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": "SpaceSuite-ISSTracker/1.0",
                "Connection": "close",
                "Accept": "application/json",
            },
            limits=httpx.Limits(max_keepalive_connections=0),
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
        """Query primary API, retry once on network disconnect, or use fallback API."""
        try:
            return self._query_primary()
        except TelemetryError as primary_err:
            logger.warning("Primary telemetry source failed (%s). Attempting fallback...", primary_err)
            try:
                return self._query_fallback()
            except (httpx.HTTPError, KeyError, ValueError, TypeError) as fallback_err:
                raise TelemetryError(
                    f"All orbital downlinks unavailable: {primary_err} | Fallback: {fallback_err}"
                ) from primary_err

    def _query_primary(self) -> ISSTelemetry:
        # Retry up to 2 times for transient socket disconnects
        last_err: Exception | None = None
        for _ in range(2):
            try:
                response = self._client.get(self.endpoint_url)
                response.raise_for_status()
                data = response.json()
                return self._parse_wheretheiss(data)
            except httpx.HTTPStatusError as err:
                raise TelemetryError(f"HTTP {err.response.status_code}") from err
            except (httpx.RequestError, httpx.HTTPError) as err:
                last_err = err
                time.sleep(0.3)
                continue
            except (KeyError, ValueError, TypeError) as err:
                raise TelemetryError(f"Malformed ISS payload: {err}") from err

        raise TelemetryError(f"Network error querying ISS API: {last_err}")

    def _query_fallback(self) -> ISSTelemetry:
        """Fallback downlink from Open-Notify."""
        response = self._client.get(self.fallback_url)
        response.raise_for_status()
        data = response.json()
        pos = data.get("iss_position", {})
        lat = float(pos["latitude"])
        lon = float(pos["longitude"])
        ts = float(data.get("timestamp", time.time()))

        return ISSTelemetry(
            name="iss (open-notify)",
            id=25544,
            latitude=lat,
            longitude=lon,
            altitude_km=420.0,
            velocity_kmh=27580.0,
            visibility="daylight",
            footprint_km=4500.0,
            timestamp=ts,
        )

    @staticmethod
    def _parse_wheretheiss(data: dict[str, Any]) -> ISSTelemetry:
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

    # Backward compatibility alias
    _parse_payload = _parse_wheretheiss
