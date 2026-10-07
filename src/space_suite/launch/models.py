"""Data models for rocket launches, mission metadata, and countdown telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class RocketInfo:
    """Rocket launch vehicle specifications."""

    name: str
    family: str
    variant: str
    full_name: str

    @property
    def display_name(self) -> str:
        return self.full_name or self.name


@dataclass(frozen=True)
class PadInfo:
    """Launchpad and spaceport geographical metadata."""

    name: str
    location_name: str
    country_code: str
    latitude: float | None = None
    longitude: float | None = None
    map_url: str | None = None
    wiki_url: str | None = None

    @property
    def full_location(self) -> str:
        return f"{self.name}, {self.location_name}"


@dataclass(frozen=True)
class MissionInfo:
    """Payload and orbital target metadata."""

    name: str
    description: str
    mission_type: str
    orbit_name: str
    orbit_abbrev: str

    @property
    def orbit_display(self) -> str:
        if self.orbit_abbrev and self.orbit_name:
            return f"{self.orbit_name} ({self.orbit_abbrev})"
        return self.orbit_name or self.orbit_abbrev or "Classified / Unspecified"


@dataclass(frozen=True)
class LaunchItem:
    """Complete launch event metadata and countdown timing."""

    id: str
    name: str
    status_name: str
    status_abbrev: str
    net_time: datetime
    provider_name: str
    provider_type: str
    rocket: RocketInfo
    pad: PadInfo
    mission: MissionInfo | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    webcast_live: bool = False
    image_url: str | None = None
    vid_urls: list[str] = field(default_factory=list)

    @property
    def is_spacex(self) -> bool:
        return (
            "spacex" in self.provider_name.lower()
            or "falcon" in self.rocket.name.lower()
            or "starship" in self.rocket.name.lower()
        )

    @property
    def is_starship(self) -> bool:
        return (
            "starship" in self.rocket.name.lower()
            or "super heavy" in self.rocket.name.lower()
        )

    @property
    def livestream_url(self) -> str | None:
        if self.vid_urls:
            return self.vid_urls[0]
        if self.is_spacex:
            return "https://x.com/SpaceX"
        return None

    def get_remaining_seconds(self, now: datetime | None = None) -> float:
        """Seconds until T-0. Negative value means T+ (flight in progress or launched)."""
        current = now or datetime.now(UTC)
        return (self.net_time - current).total_seconds()

    def get_countdown_tuple(
        self, now: datetime | None = None
    ) -> tuple[str, int, int, int, int]:
        """Returns sign ('-' or '+'), days, hours, minutes, seconds."""
        rem = self.get_remaining_seconds(now)
        sign = "-" if rem >= 0 else "+"
        total_sec = int(abs(rem))
        days = total_sec // 86400
        hours = (total_sec % 86400) // 3600
        minutes = (total_sec % 3600) // 60
        seconds = total_sec % 60
        return sign, days, hours, minutes, seconds

    def format_countdown(self, now: datetime | None = None) -> str:
        """Formatted countdown string: e.g. 'T - 01d 04h 12m 30s'."""
        sign, days, hours, minutes, seconds = self.get_countdown_tuple(now)
        if days > 0:
            return f"T {sign} {days:02d}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
        return f"T {sign} {hours:02d}h {minutes:02d}m {seconds:02d}s"
