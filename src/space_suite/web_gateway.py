"""Unified SpaceSuite Mission Control Web Gateway.

Serves all three aerospace modules under a single local HTTP server:
- /       -> Unified Mission Control Hub & System Overview
- /iss    -> Live ISS Telemetry, 3D Relative Geometry & Passing Alert
- /launch -> SpaceX & Rocket Launch Mission Control & Countdown Clock
- /lander -> Starship / Lunar Lander 2D Suicide Burn Physics Simulator
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from space_suite.iss.client import ISSClient, TelemetryError
from space_suite.iss.models import ObserverCoords
from space_suite.iss.notifier import UbuntuNotifier
from space_suite.iss.web_server import TelemetryState
from space_suite.lander.web_server import LanderSimulationState
from space_suite.launch.client import LaunchClient
from space_suite.launch.web_server import serialize_launch

logger = logging.getLogger(__name__)

HUB_STATIC_DIR = Path(__file__).parent / "web"
ISS_STATIC_DIR = Path(__file__).parent / "iss" / "web"
LAUNCH_STATIC_DIR = Path(__file__).parent / "launch" / "web"
LANDER_STATIC_DIR = Path(__file__).parent / "lander" / "web"


class UnifiedGatewayHandler(SimpleHTTPRequestHandler):
    """Routes HTTP requests across all three SpaceSuite modules."""

    iss_state: TelemetryState
    launch_client: LaunchClient
    lander_sim: LanderSimulationState

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(HUB_STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress logging for high-frequency polling
        path = args[0] if args else ""
        if "/api/" not in path:
            super().log_message(format, *args)

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # 1. Unified Hub
        if path in ("/", "/index.html", "/hub"):
            self._serve_file(HUB_STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return

        # 2. Shared Assets (Leaflet bundle)
        if path == "/leaflet.js":
            self._serve_file(ISS_STATIC_DIR / "leaflet.js", "application/javascript")
            return
        if path == "/leaflet.css":
            self._serve_file(ISS_STATIC_DIR / "leaflet.css", "text/css")
            return

        # 3. Module 1: ISS Tracker
        if path in ("/iss", "/iss/", "/iss/index.html"):
            self._serve_file(ISS_STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return

        # 4. Module 2: Launch Mission Control
        if path in ("/launch", "/launch/", "/launch/index.html"):
            self._serve_file(
                LAUNCH_STATIC_DIR / "index.html", "text/html; charset=utf-8"
            )
            return

        # 5. Module 3: Lander Suicide Burn Simulator
        if path in ("/lander", "/lander/", "/lander/index.html"):
            self._serve_file(
                LANDER_STATIC_DIR / "index.html", "text/html; charset=utf-8"
            )
            return

        # --- REST APIs ---
        # ISS Telemetry Endpoint
        if path in ("/api/iss/telemetry", "/iss/api/telemetry"):
            data = self.iss_state.get_snapshot()
            self._send_json(data)
            return

        # Launch Library 2 Endpoint
        if path in ("/api/launches", "/launch/api/launches"):
            query = urllib.parse.parse_qs(parsed_url.query)
            search_param = query.get("search", [None])[0]
            launches = self.launch_client.fetch_upcoming(search=search_param, limit=12)
            self._send_json(
                {
                    "status": "online",
                    "count": len(launches),
                    "launches": [serialize_launch(l) for l in launches],
                }
            )
            return

        # Lander Telemetry Endpoint
        if path in ("/api/telemetry", "/api/lander/telemetry", "/lander/api/telemetry"):
            # Check if this was requested by ISS page (when referring from /iss)
            referer = self.headers.get("Referer", "")
            if "/iss" in referer and "lander" not in referer:
                self._send_json(self.iss_state.get_snapshot())
                return
            self._send_json(self.lander_sim.get_snapshot())
            return

        self.send_error(HTTPStatus.NOT_FOUND, f"Path not found: {path}")

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len)

        # ISS simulation trigger
        if path in ("/api/simulate_pass", "/iss/api/simulate_pass"):
            self.iss_state.trigger_sim()
            self._send_json({"status": "simulation_triggered"})
            return

        # Lander action commands
        if path in ("/api/action", "/lander/api/action"):
            payload = json.loads(post_body.decode("utf-8")) if post_body else {}
            action = payload.get("action")
            if action == "reset":
                self.lander_sim.reset()
            elif action == "preset":
                self.lander_sim.select_preset(payload.get("preset", "starship"))
            elif action == "toggle_autopilot":
                self.lander_sim.set_autopilot(payload.get("enabled", True))
            elif action == "controls":
                self.lander_sim.set_controls(
                    float(payload.get("throttle", 0.0)),
                    float(payload.get("gimbal", 0.0)),
                )
            self._send_json({"status": "ok"})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _serve_file(self, file_path: Path, content_type: str) -> None:
        if not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)


def launch_unified_gateway(
    port: int = 8055,
    observer_lat: float = 51.5074,
    observer_lon: float = -0.1278,
    observer_name: str = "London Ground Station",
    open_browser: bool = True,
) -> None:
    """Launch background workers for all modules and start unified web server."""
    # 1. State setup
    observer = ObserverCoords(
        latitude=observer_lat, longitude=observer_lon, name=observer_name
    )
    notifier = UbuntuNotifier()
    iss_state = TelemetryState(observer, notifier, threshold_km=1000.0)
    launch_client = LaunchClient(cache_ttl_seconds=900.0)
    lander_sim = LanderSimulationState()

    UnifiedGatewayHandler.iss_state = iss_state
    UnifiedGatewayHandler.launch_client = launch_client
    UnifiedGatewayHandler.lander_sim = lander_sim

    # 2. ISS Background Telemetry Poller (0.5 Hz / 2s)
    iss_running = True

    def iss_worker() -> None:
        with ISSClient() as client:
            while iss_running:
                try:
                    telemetry = client.get_current_telemetry()
                    iss_state.update(telemetry)
                except TelemetryError as err:
                    logger.debug("ISS telemetry error: %s", err)
                time.sleep(2.0)

    iss_thread = threading.Thread(target=iss_worker, daemon=True)
    iss_thread.start()

    # 3. Lander 50 Hz Physics Loop
    def lander_worker() -> None:
        last_t = time.time()
        while lander_sim.running:
            now = time.time()
            dt = max(0.01, min(0.05, now - last_t))
            last_t = now
            lander_sim.step(dt)
            time.sleep(0.02)

    lander_thread = threading.Thread(target=lander_worker, daemon=True)
    lander_thread.start()

    # 4. HTTP Server
    url = f"http://127.0.0.1:{port}"
    server = ThreadingHTTPServer(("0.0.0.0", port), UnifiedGatewayHandler)

    print("\n=======================================================")
    print("🚀  SpaceSuite Unified Mission Control Gateway Live!")
    print("=======================================================")
    print(f"🌐  Mission Control Hub:    {url}/")
    print(f"🛰️  ISS Live Tracker:       {url}/iss")
    print(f"🔴  SpaceX Launch Control:  {url}/launch")
    print(f"🛬  Starship Lander Sim:    {url}/lander")
    print("=======================================================")
    print("Press Ctrl+C to stop all servers.\n")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down SpaceSuite Gateway...")
    finally:
        iss_running = False
        lander_sim.running = False
        launch_client.close()
        server.server_close()
