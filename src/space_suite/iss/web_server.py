"""Lightweight local web server for the visual ISS Mission Control dashboard."""

from __future__ import annotations

import json
import logging
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from space_suite.iss.client import ISSClient, TelemetryError
from space_suite.iss.models import ISSTelemetry, ObserverCoords, RelativePosition
from space_suite.iss.notifier import UbuntuNotifier
from space_suite.iss.orbital_math import (
    calculate_orbital_period_minutes,
    compute_relative_position,
)

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "web"


class TelemetryState:
    """Thread-safe state container for active telemetry and pass status."""

    def __init__(
        self,
        observer: ObserverCoords,
        notifier: UbuntuNotifier,
        threshold_km: float = 1000.0,
    ) -> None:
        self.observer = observer
        self.notifier = notifier
        self.threshold_km = threshold_km
        self.lock = threading.Lock()
        self.latest_iss: ISSTelemetry | None = None
        self.latest_rel: RelativePosition | None = None
        self.error_msg: str | None = None
        self.sim_active = False
        self.sim_start_time = 0.0

    def trigger_sim(self) -> None:
        with self.lock:
            self.sim_active = True
            self.sim_start_time = time.time()

    def update(self, iss: ISSTelemetry) -> None:
        with self.lock:
            self.latest_iss = iss
            self.latest_rel = compute_relative_position(
                self.observer,
                iss,
                threshold_km=self.threshold_km,
            )
            self.error_msg = None
            # Evaluate desktop notifications
            self.notifier.evaluate_and_notify(self.latest_rel, iss, self.observer)

    def set_error(self, err: str) -> None:
        with self.lock:
            self.error_msg = err

    def get_snapshot(self) -> dict[str, Any]:
        with self.lock:
            now = time.time()
            # If simulation is active, interpolate a simulated pass
            if self.sim_active:
                elapsed = now - self.sim_start_time
                if elapsed > 16.0:
                    self.sim_active = False
                else:
                    progress = elapsed / 16.0
                    # Trajectory passing directly over observer
                    offset = 12.0 * (1.0 - 2.0 * progress)
                    sim_iss = ISSTelemetry(
                        name="iss (simulated)",
                        id=25544,
                        latitude=self.observer.latitude + offset * 0.7,
                        longitude=self.observer.longitude + offset * 0.7,
                        altitude_km=421.0,
                        velocity_kmh=27580.0,
                        visibility="daylight",
                        footprint_km=4520.0,
                        timestamp=now,
                    )
                    rel = compute_relative_position(
                        self.observer,
                        sim_iss,
                        threshold_km=self.threshold_km,
                    )
                    self.notifier.evaluate_and_notify(rel, sim_iss, self.observer)
                    return self._serialize(sim_iss, rel)

            if not self.latest_iss or not self.latest_rel:
                return {"status": "loading", "error": self.error_msg}

            return self._serialize(self.latest_iss, self.latest_rel)

    def _serialize(self, iss: ISSTelemetry, rel: RelativePosition) -> dict[str, Any]:
        return {
            "status": "online",
            "threshold_km": self.threshold_km,
            "observer": {
                "name": self.observer.name,
                "latitude": self.observer.latitude,
                "longitude": self.observer.longitude,
                "lat_str": self.observer.lat_str,
                "lon_str": self.observer.lon_str,
            },
            "iss": {
                "name": iss.name,
                "latitude": iss.latitude,
                "longitude": iss.longitude,
                "altitude_km": iss.altitude_km,
                "velocity_kmh": iss.velocity_kmh,
                "velocity_kms": iss.velocity_kms,
                "lat_str": iss.lat_str,
                "lon_str": iss.lon_str,
                "visibility": iss.visibility,
                "is_sunlit": iss.is_sunlit,
                "footprint_km": iss.footprint_km,
                "timestamp": iss.timestamp,
                "orbital_period_mins": round(
                    calculate_orbital_period_minutes(iss.altitude_km), 2
                ),
                "orbits_per_day": round(
                    1440.0 / calculate_orbital_period_minutes(iss.altitude_km), 1
                ),
            },
            "relative": {
                "ground_distance_km": rel.ground_distance_km,
                "slant_range_km": rel.slant_range_km,
                "elevation_deg": rel.elevation_deg,
                "bearing_deg": rel.bearing_deg,
                "compass_heading": rel.compass_heading,
                "is_above_horizon": rel.is_above_horizon,
                "is_in_range": rel.is_in_range,
            },
        }


class ISSWebHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for web dashboard and API endpoints."""

    state: TelemetryState

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress routine request logs to keep terminal clean
        pass

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            index_path = STATIC_DIR / "index.html"
            self.wfile.write(index_path.read_bytes())
        elif self.path == "/leaflet.js":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            self.wfile.write((STATIC_DIR / "leaflet.js").read_bytes())
        elif self.path == "/leaflet.css":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css")
            self.end_headers()
            self.wfile.write((STATIC_DIR / "leaflet.css").read_bytes())
        elif self.path == "/api/telemetry":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            payload = json.dumps(self.state.get_snapshot())
            self.wfile.write(payload.encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/test-notify":
            success = self.state.notifier.send_test()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))
        elif self.path == "/api/simulate-pass":
            self.state.trigger_sim()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()


def telemetry_poller_thread(
    state: TelemetryState,
    interval: float,
    stop_event: threading.Event,
) -> None:
    """Continuously poll telemetry in the background."""
    with ISSClient() as client:
        while not stop_event.is_set():
            try:
                iss = client.fetch_telemetry()
                state.update(iss)
            except TelemetryError as err:
                state.set_error(str(err))
            stop_event.wait(interval)


def launch_web_server(
    observer: ObserverCoords,
    notifier: UbuntuNotifier,
    threshold_km: float = 1000.0,
    port: int = 8055,
    poll_interval: float = 2.0,
    open_browser: bool = True,
) -> None:
    """Start local dashboard web server and launch browser."""
    state = TelemetryState(
        observer=observer, notifier=notifier, threshold_km=threshold_km
    )

    # Attach state to handler class
    class BoundHandler(ISSWebHandler):
        pass

    BoundHandler.state = state

    stop_event = threading.Event()
    poller = threading.Thread(
        target=telemetry_poller_thread,
        args=(state, poll_interval, stop_event),
        daemon=True,
    )
    poller.start()

    url = f"http://127.0.0.1:{port}"
    server = ThreadingHTTPServer(("127.0.0.1", port), BoundHandler)

    print(f"\n🛰️  ISS Mission Control Web Dashboard is live at: {url}")
    print("🔔  Ubuntu Desktop Alerts (notify-send) armed and active in background.")
    print("Press Ctrl+C to terminate the server.\n")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down web server...")
    finally:
        stop_event.set()
        server.server_close()
        print("Server shutdown complete.")
