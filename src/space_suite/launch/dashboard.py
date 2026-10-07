"""Rich terminal dashboard for rocket launch countdowns and manifest telemetry."""

from __future__ import annotations

from datetime import UTC, datetime

from rich.align import Align
from rich.box import ROUNDED, SIMPLE
from rich.console import RenderableType
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from space_suite.launch.models import LaunchItem


class LaunchDashboard:
    """Renders upcoming rocket launches and live mission countdown using Rich."""

    def __init__(self, filter_name: str = "SpaceX") -> None:
        self.filter_name = filter_name

    def render(
        self,
        launches: list[LaunchItem],
        error_msg: str | None = None,
    ) -> RenderableType:
        """Construct the complete Rich Mission Control dashboard layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="featured", size=15),
            Layout(name="manifest", size=10),
            Layout(name="footer", size=3),
        )

        now = datetime.now(UTC)
        next_launch = launches[0] if launches else None

        layout["header"].update(self._render_header(now))
        layout["featured"].update(self._render_featured(next_launch, now, error_msg))
        layout["manifest"].update(
            self._render_manifest(launches[1:6] if launches else [])
        )
        layout["footer"].update(self._render_footer())

        return layout

    def _render_header(self, now: datetime) -> Panel:
        title_text = Text()
        title_text.append("🚀  SPACEX & ROCKET MISSION CONTROL ", style="bold red")
        title_text.append("• LAUNCH TELEMETRY COUNTDOWN", style="bold white")

        now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        status_text = Text(
            f"FILTER: {self.filter_name.upper()} | CLOCK: {now_str}", style="dim"
        )

        table = Table.grid(expand=True)
        table.add_column(justify="left")
        table.add_column(justify="right")
        table.add_row(title_text, status_text)

        return Panel(table, border_style="red", box=ROUNDED)

    def _render_featured(
        self,
        launch: LaunchItem | None,
        now: datetime,
        error_msg: str | None,
    ) -> Panel:
        if error_msg:
            return Panel(
                Align.center(
                    f"[bold red]⚠️ Telemetry Signal Interrupted[/]\n\n[yellow]{error_msg}[/]"
                ),
                title="Launch Link Warning",
                border_style="red",
                box=ROUNDED,
            )

        if not launch:
            return Panel(
                Align.center(
                    "[yellow]Awaiting upcoming rocket launch manifest downlink...[/]"
                ),
                box=ROUNDED,
            )

        # Big countdown banner
        cd_str = launch.format_countdown(now)
        rem_sec = launch.get_remaining_seconds(now)

        cd_style = "bold green" if rem_sec > 0 else "bold red"
        cd_title = Text()
        cd_title.append("T-MINUS COUNTDOWN: ", style="bold dim")
        cd_title.append(f"{cd_str}\n", style=f"{cd_style} underline")

        # Two-column layout for vehicle metadata and mission dossier
        meta_table = Table(box=SIMPLE, expand=True, show_header=False)
        meta_table.add_column("Property", style="cyan", width=22)
        meta_table.add_column("Value", style="bold white")

        meta_table.add_row("Mission Name", launch.name)
        meta_table.add_row(
            "Launch Provider",
            f"{launch.provider_name} [dim]({launch.provider_type})[/]",
        )
        meta_table.add_row("Rocket Vehicle", launch.rocket.display_name)
        if launch.is_starship:
            meta_table.add_row(
                "Vehicle Class",
                "[bold magenta]⭐ Starship Super Heavy (Next-Gen Heavy Lift)[/]",
            )
        elif launch.is_spacex:
            meta_table.add_row(
                "Vehicle Class", "[bold cyan]Falcon Reusable Booster Architecture[/]"
            )

        meta_table.add_row(
            "Target NET Liftoff",
            f"{launch.net_time.strftime('%Y-%m-%d %H:%M:%S UTC')} [dim]({launch.status_name})[/]",
        )
        meta_table.add_row("Launchpad & Pad", launch.pad.full_location)

        if launch.mission:
            meta_table.add_row("Target Orbit", launch.mission.orbit_display)
            meta_table.add_row("Payload Type", launch.mission.mission_type)

        if launch.livestream_url:
            meta_table.add_row(
                "Webcast Stream", f"[underline blue]{launch.livestream_url}[/]"
            )

        # Combine countdown and metadata
        container = Table.grid(expand=True)
        container.add_column()
        container.add_row(Align.center(cd_title))
        container.add_row(meta_table)

        status_badge = (
            "[bold green]● GO FOR LAUNCH[/]"
            if "go" in launch.status_name.lower()
            else f"[yellow]● {launch.status_name.upper()}[/]"
        )
        return Panel(
            container,
            title=f"[bold red]★ Upcoming Primary Mission: {launch.rocket.name} | {status_badge}",
            border_style="red",
            box=ROUNDED,
        )

    def _render_manifest(self, next_launches: list[LaunchItem]) -> Panel:
        table = Table(box=SIMPLE, expand=True)
        table.add_column("NET Date (UTC)", style="cyan")
        table.add_column("Rocket", style="bold white")
        table.add_column("Provider")
        table.add_column("Mission")
        table.add_column("Launch Site", style="dim")
        table.add_column("Countdown", justify="right", style="bold yellow")

        now = datetime.now(UTC)
        if not next_launches:
            table.add_row(
                "—", "—", "—", "No additional launches queued in manifest", "—", "—"
            )
        else:
            for item in next_launches:
                table.add_row(
                    item.net_time.strftime("%Y-%m-%d %H:%M"),
                    item.rocket.display_name,
                    item.provider_name,
                    item.mission.name if item.mission else item.name,
                    item.pad.location_name,
                    item.format_countdown(now),
                )

        return Panel(
            table,
            title="[bold yellow]● Upcoming Global Launch Manifest (Queue)[/]",
            border_style="yellow",
            box=ROUNDED,
        )

    def _render_footer(self) -> Panel:
        footer_text = Text.from_markup(
            "Controls: Press [bold red]Ctrl+C[/] to exit | "
            "Downlink: [cyan]Launch Library 2 (SpaceDevs)[/]"
        )
        return Panel(Align.center(footer_text), border_style="dim", box=ROUNDED)
