"""Main CLI entry point for the Starship & Lander Suicide Burn Simulator."""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from space_suite.lander.models import PlanetaryEnvironment, VehicleConfig

from rich.console import Console
from rich.live import Live

from space_suite.lander.autopilot import SuicideBurnAutopilot
from space_suite.lander.dashboard import LanderTerminalDashboard
from space_suite.lander.models import (
    APOLLO_LUNAR_MODULE,
    EARTH,
    FALCON_9_BOOSTER,
    MARS,
    MOON,
    STARSHIP_SUPER_HEAVY,
)
from space_suite.lander.physics import LanderPhysicsEngine


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lander",
        description="SpaceSuite Starship & Lunar Lander 2D Suicide Burn Physics Simulator",
    )
    parser.add_argument(
        "-w",
        "--web",
        action="store_true",
        help="Launch interactive web browser Mission Control simulator",
    )
    parser.add_argument(
        "-t",
        "--terminal",
        action="store_true",
        help="Run in pure terminal mode using Rich Live aerospace HUD",
    )
    parser.add_argument(
        "-g",
        "--gui",
        action="store_true",
        help="Run in native desktop Pygame 60 FPS graphical window (default)",
    )
    parser.add_argument(
        "-v",
        "--vehicle",
        choices=["starship", "falcon9", "lunar"],
        default="starship",
        help="Vehicle preset (default: starship)",
    )
    parser.add_argument(
        "-e",
        "--env",
        choices=["earth", "moon", "mars"],
        default="earth",
        help="Planetary environment (default: earth)",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Start in manual pilot mode instead of automated suicide burn GNC",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8057,
        help="Port for web dashboard (default: 8057)",
    )
    return parser.parse_args(argv)


def get_vehicle_and_env(
    vehicle_arg: str, env_arg: str
) -> tuple[VehicleConfig, PlanetaryEnvironment]:
    v_map = {
        "starship": STARSHIP_SUPER_HEAVY,
        "falcon9": FALCON_9_BOOSTER,
        "lunar": APOLLO_LUNAR_MODULE,
    }
    e_map = {
        "earth": EARTH,
        "moon": MOON,
        "mars": MARS,
    }
    veh = v_map.get(vehicle_arg, STARSHIP_SUPER_HEAVY)
    env = e_map.get(env_arg, EARTH)
    if vehicle_arg == "lunar" and env_arg == "earth":
        env = MOON  # Default lunar module to moon
    return veh, env


def run_terminal_mode(
    vehicle: VehicleConfig, env: PlanetaryEnvironment, autopilot_on: bool
) -> int:
    """Run simulation directly inside the terminal with Rich Live HUD."""
    console = Console()
    physics = LanderPhysicsEngine(vehicle, env)
    autopilot = SuicideBurnAutopilot(physics)

    initial_alt = (
        600.0
        if vehicle == APOLLO_LUNAR_MODULE
        else (1000.0 if vehicle == FALCON_9_BOOSTER else 850.0)
    )
    initial_vy = -40.0 if vehicle == APOLLO_LUNAR_MODULE else -75.0

    from space_suite.lander.models import FlightTelemetry

    telem = FlightTelemetry(
        y=initial_alt,
        vy=initial_vy,
        x=15.0,
        vx=1.2,
        fuel=vehicle.fuel_capacity * 0.45,
        autopilot_enabled=autopilot_on,
    )

    dashboard = LanderTerminalDashboard(vehicle, env)
    dt = 0.05

    console.print(
        f"\n[bold cyan]🚀 Starting {vehicle.name} descent simulation on {env.name}...[/]"
    )
    console.print("[dim]Press Ctrl+C to stop simulation.[/]\n")

    try:
        with Live(
            dashboard.render(telem, 0.0), refresh_per_second=20, console=console
        ) as live:
            while not telem.is_touchdown:
                time.sleep(dt)
                burn_alt = physics.calculate_suicide_burn_altitude(telem)
                if telem.autopilot_enabled:
                    cmd = autopilot.compute(telem)
                    telem.throttle = cmd.throttle
                    telem.gimbal_deg = cmd.gimbal_deg
                    telem.rcs_command = cmd.rcs_command
                    burn_alt = cmd.burn_altitude

                telem = physics.step(telem, dt=dt)
                live.update(dashboard.render(telem, burn_alt))

            # Final frame after touchdown
            burn_alt = physics.calculate_suicide_burn_altitude(telem)
            live.update(dashboard.render(telem, burn_alt))

    except KeyboardInterrupt:
        console.print("\n[yellow]Simulation halted by user.[/]")
        return 0

    if telem.status.value == "LANDED":
        console.print(f"\n[bold green]✅ {telem.status_detail}[/]\n")
    else:
        console.print(f"\n[bold red]💥 {telem.status_detail}[/]\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    console = Console()
    vehicle, env = get_vehicle_and_env(args.vehicle, args.env)

    # 1. Web Dashboard Mode
    if args.web:
        console.print(
            f"\n[bold cyan]🚀 Launching Lander Web Mission Control on port {args.port}...[/]"
        )
        console.print(
            f"🔗 Open browser at: [bold green]http://127.0.0.1:{args.port}[/]"
        )
        console.print("[dim]Press Ctrl+C to terminate server.[/]\n")
        from space_suite.lander.web_server import start_lander_web_server

        try:
            start_lander_web_server(port=args.port)
        except KeyboardInterrupt:
            console.print("\n[yellow]Web server terminated.[/]")
            return 0

    # 2. Terminal HUD Mode
    if args.terminal:
        return run_terminal_mode(vehicle, env, autopilot_on=not args.manual)

    # 3. Graphical Pygame Mode (Default when graphical display is available)
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    if not has_display:
        console.print(
            "[yellow]No graphical display detected ($DISPLAY empty). Running in Rich terminal mode...[/]"
        )
        return run_terminal_mode(vehicle, env, autopilot_on=not args.manual)

    try:
        from space_suite.lander.renderer_pygame import LanderPygameRenderer

        renderer = LanderPygameRenderer(
            vehicle=vehicle,
            env=env,
            start_autopilot=not args.manual,
        )
        renderer.run()
    except (RuntimeError, OSError) as exc:
        console.print(
            f"[yellow]Graphical window error ({exc}). Falling back to terminal mode...[/]"
        )
        return run_terminal_mode(vehicle, env, autopilot_on=not args.manual)


if __name__ == "__main__":
    sys.exit(main())
