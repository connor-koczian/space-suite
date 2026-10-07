"""Interactive Web Mission Control server for the Lander Suicide Burn Simulator."""

from __future__ import annotations

import http.server
import json
import math
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from space_suite.lander.autopilot import SuicideBurnAutopilot
from space_suite.lander.models import (
    APOLLO_LUNAR_MODULE,
    EARTH,
    FALCON_9_BOOSTER,
    MOON,
    STARSHIP_SUPER_HEAVY,
    FlightTelemetry,
    PlanetaryEnvironment,
    VehicleConfig,
)
from space_suite.lander.physics import LanderPhysicsEngine

WEB_DIR = Path(__file__).parent / "web"


class LanderSimulationState:
    """Thread-safe simulation state machine running at 50 Hz."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.vehicle: VehicleConfig = STARSHIP_SUPER_HEAVY
        self.env: PlanetaryEnvironment = EARTH
        self.physics = LanderPhysicsEngine(self.vehicle, self.env)
        self.autopilot = SuicideBurnAutopilot(self.physics)
        self.telemetry = self._new_flight()
        self.manual_throttle = 0.0
        self.manual_gimbal = 0.0
        self.running = True

    def _new_flight(self) -> FlightTelemetry:
        if self.vehicle == APOLLO_LUNAR_MODULE:
            return FlightTelemetry(
                y=600.0,
                vy=-40.0,
                x=-10.0,
                vx=-0.8,
                theta=math.radians(-0.8),
                fuel=5000.0,
                autopilot_enabled=True,
            )
        elif self.vehicle == FALCON_9_BOOSTER:
            return FlightTelemetry(
                y=1000.0,
                vy=-85.0,
                x=8.0,
                vx=0.5,
                theta=0.0,
                fuel=18000.0,
                autopilot_enabled=True,
            )
        else:
            return FlightTelemetry(
                y=850.0,
                vy=-75.0,
                x=18.0,
                vx=1.2,
                theta=math.radians(1.2),
                fuel=30000.0,
                autopilot_enabled=True,
            )

    def reset(self) -> None:
        with self.lock:
            self.physics = LanderPhysicsEngine(self.vehicle, self.env)
            self.autopilot = SuicideBurnAutopilot(self.physics)
            self.telemetry = self._new_flight()

    def select_preset(self, preset: str) -> None:
        with self.lock:
            if preset == "falcon9":
                self.vehicle = FALCON_9_BOOSTER
                self.env = EARTH
            elif preset == "lunar":
                self.vehicle = APOLLO_LUNAR_MODULE
                self.env = MOON
            else:
                self.vehicle = STARSHIP_SUPER_HEAVY
                self.env = EARTH
            self.physics = LanderPhysicsEngine(self.vehicle, self.env)
            self.autopilot = SuicideBurnAutopilot(self.physics)
            self.telemetry = self._new_flight()

    def set_autopilot(self, enabled: bool) -> None:
        with self.lock:
            self.telemetry.autopilot_enabled = enabled
            if not enabled:
                self.autopilot.reset()

    def set_controls(self, throttle: float, gimbal: float) -> None:
        with self.lock:
            self.manual_throttle = max(0.0, min(1.0, throttle))
            self.manual_gimbal = max(
                -self.vehicle.max_gimbal_deg, min(self.vehicle.max_gimbal_deg, gimbal)
            )

    def step(self, dt: float) -> None:
        with self.lock:
            if self.telemetry.autopilot_enabled and not self.telemetry.is_touchdown:
                cmd = self.autopilot.compute(self.telemetry)
                self.telemetry.throttle = cmd.throttle
                self.telemetry.gimbal_deg = cmd.gimbal_deg
                self.telemetry.rcs_command = cmd.rcs_command
            elif (
                not self.telemetry.autopilot_enabled and not self.telemetry.is_touchdown
            ):
                self.telemetry.throttle = self.manual_throttle
                self.telemetry.gimbal_deg = self.manual_gimbal

            self.telemetry = self.physics.step(self.telemetry, dt=dt)

    def get_snapshot(self) -> dict:
        with self.lock:
            burn_alt = self.physics.calculate_suicide_burn_altitude(self.telemetry)
            return {
                "time": round(self.telemetry.time, 2),
                "vehicle": self.vehicle.name,
                "environment": self.env.name,
                "gravity": round(self.env.gravity, 2),
                "pad_width": self.env.pad_width,
                "x": round(self.telemetry.x, 2),
                "y": round(self.telemetry.y, 2),
                "vx": round(self.telemetry.vx, 2),
                "vy": round(self.telemetry.vy, 2),
                "speed": round(self.telemetry.speed, 2),
                "theta_deg": round(self.telemetry.pitch_degrees, 2),
                "throttle": round(self.telemetry.throttle, 2),
                "gimbal_deg": round(self.telemetry.gimbal_deg, 2),
                "fuel": round(self.telemetry.fuel, 0),
                "fuel_capacity": self.vehicle.fuel_capacity,
                "legs_deployed": self.telemetry.legs_deployed,
                "autopilot": self.telemetry.autopilot_enabled,
                "status": self.telemetry.status.value,
                "status_detail": self.telemetry.status_detail,
                "suicide_burn_alt": round(burn_alt, 1),
                "history": [
                    (round(px, 1), round(py, 1))
                    for px, py in self.telemetry.trajectory_history[-80:]
                ],
            }


class LanderWebHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler serving the lander simulator UI and REST telemetry."""

    sim_state: LanderSimulationState

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/telemetry":
            data = self.sim_state.get_snapshot()
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len)

        if parsed.path == "/api/action":
            payload = json.loads(post_body.decode("utf-8")) if post_body else {}
            action = payload.get("action")

            if action == "reset":
                self.sim_state.reset()
            elif action == "preset":
                self.sim_state.select_preset(payload.get("preset", "starship"))
            elif action == "toggle_autopilot":
                enabled = payload.get("enabled", True)
                self.sim_state.set_autopilot(enabled)
            elif action == "controls":
                thr = float(payload.get("throttle", 0.0))
                gimb = float(payload.get("gimbal", 0.0))
                self.sim_state.set_controls(thr, gimb)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        self.send_error(404, "Not Found")

    def log_message(self, format: str, *args) -> None:
        # Suppress routine GET logging for sub-second telemetry polls
        if "/api/telemetry" not in (args[0] if args else ""):
            super().log_message(format, *args)


def start_lander_web_server(port: int = 8057) -> None:
    """Launch the 50 Hz physics loop and HTTP server on the designated port."""
    sim = LanderSimulationState()
    LanderWebHandler.sim_state = sim

    # Background physics loop (50 Hz / 20ms step)
    def physics_worker() -> None:
        last_t = time.time()
        while sim.running:
            now = time.time()
            dt = now - last_t
            last_t = now
            dt = max(0.01, min(0.05, dt))
            sim.step(dt)
            time.sleep(0.02)

    p_thread = threading.Thread(target=physics_worker, daemon=True)
    p_thread.start()

    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), LanderWebHandler)
    server.serve_forever()
