"""Main launch mission control orchestrator and CLI application."""

from __future__ import annotations

import argparse
import sys
import time

from rich.console import Console
from rich.live import Live

from space_suite.launch.client import LaunchAPIError, LaunchClient
from space_suite.launch.dashboard import LaunchDashboard


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SpaceSuite Rocket Mission Control: Live countdown clocks, vehicle telemetry, and launch manifest.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--filter",
        "-f",
        type=str,
        default="SpaceX",
        help="Search filter for rocket, provider, or mission (e.g. 'SpaceX', 'Starship', 'NASA', 'all')",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=8,
        help="Number of upcoming launches to queue in manifest",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Clock tick interval in seconds",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch interactive visual web countdown clock with launchpad satellite map",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8056,
        help="Local port for web dashboard (default: 8056)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    console = Console()

    filter_query = None if args.filter.lower() == "all" else args.filter

    if args.web:
        from space_suite.launch.web_server import launch_web_server

        launch_web_server(
            search=filter_query,
            port=args.port,
            open_browser=True,
        )
        return 0

    dashboard = LaunchDashboard(filter_name=args.filter)
    console.print(
        f"[bold red]Downlinking upcoming launches for '{args.filter}'... Press Ctrl+C to exit.[/]"
    )

    error_msg: str | None = None
    last_launches = []
    last_api_poll = 0.0

    try:
        with (
            LaunchClient() as client,
            Live(console=console, screen=True, refresh_per_second=2) as live,
        ):
            while True:
                now = time.time()
                # Re-query API every 60 seconds
                if now - last_api_poll >= 60.0 or not last_launches:
                    try:
                        last_launches = client.fetch_upcoming(
                            search=filter_query,
                            limit=args.limit,
                        )
                        error_msg = None
                        last_api_poll = now
                    except LaunchAPIError as err:
                        error_msg = str(err)

                renderable = dashboard.render(
                    launches=last_launches,
                    error_msg=error_msg,
                )
                live.update(renderable)
                time.sleep(args.interval)

    except KeyboardInterrupt:
        console.print(
            "\n[bold yellow]Launch Mission Control terminated by operator. Standby.[/]"
        )
        return 0
    except (OSError, RuntimeError) as err:
        console.print(f"\n[bold red]Fatal error in mission control loop:[/] {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
