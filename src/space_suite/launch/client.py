"""Client for querying upcoming rocket launches from Launch Library 2."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Self

import httpx

from space_suite.launch.models import LaunchItem, MissionInfo, PadInfo, RocketInfo

logger = logging.getLogger(__name__)

LAUNCH_API_BASE: str = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/"
DEFAULT_TIMEOUT: float = 8.0


class LaunchAPIError(Exception):
    """Raised when rocket launch data cannot be fetched."""


class LaunchClient:
    """Queries upcoming rocket missions with caching and offline fallback."""

    def __init__(
        self,
        base_url: str = LAUNCH_API_BASE,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self._external_client = client is not None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": "SpaceSuite-LaunchControl/1.0",
                "Accept": "application/json",
            },
        )
        self.cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[float, list[LaunchItem]]] = {}

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
        if not self._external_client:
            self._client.close()

    def fetch_upcoming(
        self,
        search: str | None = None,
        limit: int = 10,
        force_refresh: bool = False,
    ) -> list[LaunchItem]:
        """Fetch upcoming launches. Returns cached results if within TTL."""
        cache_key = f"{search or 'all'}_{limit}"
        now = time.time()

        if not force_refresh and cache_key in self._cache:
            ts, cached_data = self._cache[cache_key]
            if now - ts < self.cache_ttl:
                return cached_data

        params: dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search

        try:
            response = self._client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            launches = [self._parse_launch(item) for item in data.get("results", [])]
            self._cache[cache_key] = (now, launches)
            return launches
        except Exception as err:
            logger.warning("Error fetching launches (%s). Checking cache fallback...", err)
            if cache_key in self._cache:
                return self._cache[cache_key][1]
            raise LaunchAPIError(f"Failed to fetch upcoming launches: {err}") from err

    @staticmethod
    def _parse_launch(data: dict[str, Any]) -> LaunchItem:
        """Parse raw Launch Library 2 JSON into LaunchItem model."""
        # Parse NET datetime
        net_str = data.get("net", "")
        try:
            net_time = datetime.fromisoformat(net_str)
        except (ValueError, TypeError):
            net_time = datetime.now(UTC)

        # Window times
        window_start = None
        if data.get("window_start"):
            try:
                window_start = datetime.fromisoformat(data["window_start"])
            except ValueError:
                pass

        window_end = None
        if data.get("window_end"):
            try:
                window_end = datetime.fromisoformat(data["window_end"])
            except ValueError:
                pass

        # Rocket info
        rocket_data = data.get("rocket", {})
        config_data = rocket_data.get("configuration", {})
        rocket = RocketInfo(
            name=config_data.get("name", "Unknown Rocket"),
            family=config_data.get("family", ""),
            variant=config_data.get("variant", ""),
            full_name=config_data.get("full_name", config_data.get("name", "Unknown Rocket")),
        )

        # Pad info
        pad_data = data.get("pad", {})
        loc_data = pad_data.get("location", {})
        pad = PadInfo(
            name=pad_data.get("name", "Launch Complex"),
            location_name=loc_data.get("name", "Unknown Location"),
            country_code=pad_data.get("country_code", "USA"),
            latitude=float(pad_data["latitude"]) if pad_data.get("latitude") else None,
            longitude=float(pad_data["longitude"]) if pad_data.get("longitude") else None,
            map_url=pad_data.get("map_url"),
            wiki_url=pad_data.get("wiki_url"),
        )

        # Mission info
        mission_data = data.get("mission")
        mission = None
        if mission_data:
            orbit_data = mission_data.get("orbit", {})
            mission = MissionInfo(
                name=mission_data.get("name", "Classified Payload"),
                description=mission_data.get("description", "No mission description provided."),
                mission_type=mission_data.get("type", "General Orbital"),
                orbit_name=orbit_data.get("name", ""),
                orbit_abbrev=orbit_data.get("abbrev", ""),
            )

        # Livestream URLs
        vid_urls: list[str] = []
        for vid in data.get("vid_urls", []):
            if isinstance(vid, dict) and "url" in vid:
                vid_urls.append(vid["url"])
            elif isinstance(vid, str):
                vid_urls.append(vid)

        # Provider
        lsp_data = data.get("launch_service_provider", {})
        provider_name = lsp_data.get("name", "SpaceX")
        provider_type = lsp_data.get("type", "Commercial")

        status_data = data.get("status", {})
        return LaunchItem(
            id=str(data.get("id", "")),
            name=str(data.get("name", "Rocket Launch")),
            status_name=str(status_data.get("name", "Go for Launch")),
            status_abbrev=str(status_data.get("abbrev", "Go")),
            net_time=net_time,
            provider_name=provider_name,
            provider_type=provider_type,
            rocket=rocket,
            pad=pad,
            mission=mission,
            window_start=window_start,
            window_end=window_end,
            webcast_live=bool(data.get("webcast_live", False)),
            image_url=data.get("image"),
            vid_urls=vid_urls,
        )
