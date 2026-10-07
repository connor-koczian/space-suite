"""Main ISS tracking orchestrator and CLI application."""

from __future__ import annotations

import argparse
import sys
import time

from rich.console import Console
from rich.live import Live

from space_suite.iss.client import ISSClient, TelemetryError
from space_suite.iss.dashboard import ISSDashboard
from space_suite.iss.models import ISSTelemetry, ObserverCoords
from space_suite.iss.notifier import UbuntuNotifier
from space_suite.iss.orbital_math import compute_relative_position


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SpaceSuite ISS Tracker: Real-time telemetry, 3D orbital relativity, and Ubuntu pass alerts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--lat",
        type=float,
        default=51.5074,
        help="Home ground station latitude in decimal degrees (-90 to 90)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        default=-0.1278,
        help="Home ground station longitude in decimal degrees (-180 to 180)",
    )
    parser.add_argument(
        "--alt",
        type=float,
        default=0.0,
        help="Home ground station altitude in kilometers above sea level",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="Home Ground Station",
        help="Descriptive name for your ground station",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=1000.0,
        help="Pass alert threshold in kilometers (surface distance)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Telemetry polling interval in seconds",
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="Send an immediate test desktop notification and exit",
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Disable Ubuntu desktop notifications",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch interactive visual web dashboard in browser with live world map & telemetry HUD",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8055,
        help="Local port for web dashboard (default: 8055)",
    )
    parser.add_argument(
        "--simulate-pass",
        action="store_true",
        help="Run a 15-second simulated overhead pass for demonstration and testing",
    )
    return parser.parse_args(argv)


def run_simulation(
    observer: ObserverCoords,
    notifier: UbuntuNotifier,
    threshold_km: float,
) -> None:
    """Simulate an overhead pass trajectory across 15 seconds to verify UI and notifications."""
    console = Console()
    dashboard = ISSDashboard(observer=observer, threshold_km=threshold_km)

    # Simulated trajectory approaching from southwest to northeast right over the observer
    sim_steps = [
        # (lat_offset, lon_offset, alt, vel, vis, label)
        (-10.0, -10.0, 420.0, 27600.0, "daylight"),
        (-6.0, -6.0, 420.0, 27600.0, "daylight"),
        (-3.0, -3.0, 420.5, 27590.0, "daylight"),
        (-1.0, -1.0, 421.0, 27580.0, "daylight"),  # enters range!
        (0.0, 0.0, 421.5, 27580.0, "daylight"),    # direct zenith!
        (1.5, 1.5, 421.0, 27580.0, "daylight"),    # exiting
        (4.0, 4.0, 420.5, 27590.0, "daylight"),
        (8.0, 8.0, 420.0, 27600.0, "daylight"),
    ]

    console.print("[bold yellow]🚀 Initiating Simulated ISS Pass Trajectory...[/]")
    with Live(console=console, screen=True, refresh_per_second=4) as live:
        for idx, (d_lat, d_lon, alt, vel, vis) in enumerate(sim_steps):
            telemetry = ISSTelemetry(
                name="iss",
                id=25544,
                latitude=observer.latitude + d_lat,
                longitude=observer.longitude + d_lon,
                altitude_km=alt,
                velocity_kmh=vel,
                visibility=vis,
                footprint_km=4500.0,
                timestamp=time.time(),
            )
            rel = compute_relative_position(observer, telemetry, threshold_km=threshold_km)
            dashboard.record_history(telemetry, rel)
            notifier.evaluate_and_notify(rel, telemetry, observer)

            renderable = dashboard.render(
                iss=telemetry,
                rel=rel,
                poll_interval=1.5,
                notifier_active=notifier.enabled and notifier.is_available,
            )
            live.update(renderable)
            time.sleep(1.5)

    console.print("\n[bold green]✓ Simulated ISS pass completed successfully![/]")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    console = Console()

    # Initialize observer and notifier
    try:
        observer = ObserverCoords(
            latitude=args.lat,
            longitude=args.lon,
            altitude_km=args.alt,
            name=args.name,
        )
    except ValueError as err:
        console.print(f"[bold red]Configuration error:[/] {err}")
        return 1

    notifier = UbuntuNotifier(
        app_name="SpaceSuite ISS Tracker",
        enabled=not args.no_notify,
    )

    if args.test_notify:
        console.print("[cyan]Testing Ubuntu desktop notification via notify-send...[/]")
        if not notifier.is_available:
            console.print("[bold red]Error:[/] notify-send binary not found on PATH.")
            return 1
        success = notifier.send_test()
        if success:
            console.print("[bold green]✓ Notification sent! Check your Ubuntu desktop banner.[/]")
            return 0
        console.print("[bold red]Failed to dispatch notification via notify-send.[/]")
        return 1

    if args.simulate_pass:
        run_simulation(observer, notifier, args.threshold)
        return 0

    if args.web:
        from space_suite.iss.web_server import launch_web_server

        launch_web_server(
            observer=observer,
            notifier=notifier,
            threshold_km=args.threshold,
            port=args.port,
            poll_interval=args.interval,
            open_browser=True,
        )
        return 0

    dashboard = ISSDashboard(observer=observer, threshold_km=args.threshold)

    console.print("[bold cyan]Connecting to ISS telemetry stream... Press Ctrl+C to exit.[/]")

    error_msg: str | None = None
    last_iss: ISSTelemetry | None = None
    last_rel = None

    try:
        with (
            ISSClient() as client,
            Live(console=console, screen=True, refresh_per_second=4) as live,
        ):
            while True:
                try:
                    iss = client.fetch_telemetry()
                    rel = compute_relative_position(observer, iss, threshold_km=args.threshold)
                    dashboard.record_history(iss, rel)
                    notifier.evaluate_and_notify(rel, iss, observer)
                    error_msg = None
                    last_iss = iss
                    last_rel = rel
                except TelemetryError as err:
                    error_msg = str(err)

                renderable = dashboard.render(
                    iss=last_iss,
                    rel=last_rel,
                    error_msg=error_msg,
                    poll_interval=args.interval,
                    notifier_active=notifier.enabled and notifier.is_available,
                )
                live.update(renderable)
                time.sleep(args.interval)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]ISS tracking session terminated by operator. Standby.[/]")
        return 0
    except (OSError, RuntimeError) as err:
        console.print(f"\n[bold red]Fatal error in tracking loop:[/] {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
