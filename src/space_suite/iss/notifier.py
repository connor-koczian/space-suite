"""Ubuntu desktop notification dispatcher via notify-send."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time

from space_suite.iss.models import ISSTelemetry, ObserverCoords, RelativePosition

logger = logging.getLogger(__name__)


class UbuntuNotifier:
    """Dispatches native Ubuntu desktop notifications via notify-send with debouncing."""

    def __init__(
        self,
        app_name: str = "SpaceSuite ISS Tracker",
        cooldown_seconds: float = 900.0,  # 15 minutes between alerts
        enabled: bool = True,
    ) -> None:
        self.app_name = app_name
        self.cooldown_seconds = cooldown_seconds
        self.enabled = enabled
        self._notify_bin: str | None = shutil.which("notify-send")
        self._was_in_range: bool = False
        self._last_alert_timestamp: float = 0.0

    @property
    def is_available(self) -> bool:
        """Returns True if notify-send binary is found on PATH."""
        return self._notify_bin is not None

    def send_notification(
        self,
        summary: str,
        body: str,
        urgency: str = "normal",
        icon: str = "weather-clear-night",
        expire_time_ms: int = 8000,
    ) -> bool:
        """Send a desktop notification using notify-send.

        Args:
            summary: Notification title.
            body: Notification body text.
            urgency: One of 'low', 'normal', 'critical'.
            icon: Freedesktop icon name.
            expire_time_ms: Time before notification auto-dismisses.

        Returns:
            True if dispatched successfully, False otherwise.
        """
        if not self.enabled:
            return False

        if not self._notify_bin:
            logger.warning(
                "notify-send binary not found. Desktop notification skipped."
            )
            return False

        cmd = [
            self._notify_bin,
            "-a",
            self.app_name,
            "-u",
            urgency,
            "-t",
            str(expire_time_ms),
            "-i",
            icon,
            summary,
            body,
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                logger.info("Dispatched notification: %s - %s", summary, body)
                return True
            logger.error("notify-send returned code %d: %s", res.returncode, res.stderr)
            return False
        except (subprocess.SubprocessError, OSError) as err:
            logger.error("Failed to execute notify-send: %s", err)
            return False

    def send_test(self) -> bool:
        """Send an immediate test notification."""
        return self.send_notification(
            summary="🛰️ ISS Tracker Test Alert",
            body="SpaceSuite notification system is operational on Ubuntu!",
            urgency="normal",
            icon="weather-clear-night",
        )

    def evaluate_and_notify(
        self,
        rel: RelativePosition,
        iss: ISSTelemetry,
        obs: ObserverCoords,
    ) -> bool:
        """Check relative telemetry and fire notification if ISS newly enters visible range.

        Debounced to prevent notification spamming on every polling cycle.
        """
        now = time.time()
        dispatched = False

        # Transition: Entered visible range
        if rel.is_in_range and not self._was_in_range:
            time_since_last = now - self._last_alert_timestamp
            if time_since_last >= self.cooldown_seconds:
                title = f"🛰️ ISS OVERHEAD PASS: {obs.name}"
                body = (
                    f"Distance: {rel.ground_distance_km:.1f} km ({rel.slant_range_km:.1f} km direct)\n"
                    f"Elevation: {rel.elevation_deg:.1f}° | Heading: {rel.compass_heading} ({rel.bearing_deg:.0f}°)\n"
                    f"Speed: {iss.velocity_kmh:,.0f} km/h | {iss.visibility.upper()}"
                )
                urgency = "critical" if rel.elevation_deg >= 30.0 else "normal"
                dispatched = self.send_notification(
                    summary=title,
                    body=body,
                    urgency=urgency,
                    icon="weather-clear-night",
                    expire_time_ms=12000,
                )
                self._last_alert_timestamp = now

        # Update in-range tracker
        self._was_in_range = rel.is_in_range
        return dispatched
