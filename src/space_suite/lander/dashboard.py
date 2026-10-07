"""Rich terminal telemetry dashboard for headless / CLI lander simulation."""

from __future__ import annotations

import math

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from space_suite.lander.models import (
    FlightStatus,
    FlightTelemetry,
    PlanetaryEnvironment,
    VehicleConfig,
)


class LanderTerminalDashboard:
    """Renders a live aerospace HUD in the terminal using Rich."""

    def __init__(self, vehicle: VehicleConfig, env: PlanetaryEnvironment) -> None:
        self.vehicle = vehicle
        self.env = env
        self.console = Console()

    def render(self, telem: FlightTelemetry, suicide_burn_alt: float) -> Panel:
        """Create the Rich Panel containing full vehicle telemetry."""
        # Header banner
        header_table = Table.grid(expand=True)
        header_table.add_column(ratio=1)
        header_table.add_column(ratio=1, justify="right")

        mode_str = (
            "[bold green]AUTOPILOT GNC ENGAGED[/]"
            if telem.autopilot_enabled
            else "[bold yellow]MANUAL PILOT[/]"
        )
        header_table.add_row(
            f"[bold cyan]🚀 {self.vehicle.name}[/]  [dim]|[/]  [magenta]{self.env.name}[/]",
            f"Mode: {mode_str}  [dim]|[/]  T+{telem.time:05.1f}s",
        )

        # Status badge
        status_color = "cyan"
        if telem.status == FlightStatus.BURNING:
            status_color = "bright_yellow"
        elif telem.status == FlightStatus.LANDED:
            status_color = "bold green"
        elif telem.status == FlightStatus.CRASHED:
            status_color = "bold red"

        status_text = Text()
        status_text.append(f"STATUS: {telem.status.value}", style=status_color)
        status_text.append(f" — {telem.status_detail}", style="dim white")

        # Telemetry metrics grid
        telemetry_table = Table(box=None, expand=True, show_header=False)
        telemetry_table.add_column(ratio=1)
        telemetry_table.add_column(ratio=1)
        telemetry_table.add_column(ratio=1)

        # Altitude & suicide burn
        alt_str = f"[bold white]{telem.y:6.1f} m[/]"
        burn_str = (
            f"[bold yellow]{suicide_burn_alt:6.1f} m[/]"
            if suicide_burn_alt < 5000.0
            else "[dim]N/A[/]"
        )
        burn_delta = telem.y - suicide_burn_alt
        burn_alert = (
            "[bold red]IGNITION ZONE![/]"
            if (telem.y <= suicide_burn_alt and not telem.is_touchdown)
            else f"[dim]+{burn_delta:.0f}m to burn[/]"
        )

        # Velocities
        vy_color = (
            "green"
            if abs(telem.vy) <= 4.0
            else ("yellow" if abs(telem.vy) <= 15.0 else "red")
        )
        vy_str = f"[{vy_color}]{telem.vy:+.1f} m/s[/]"

        vx_color = "green" if abs(telem.vx) <= 1.8 else "red"
        vx_str = f"[{vx_color}]{telem.vx:+.1f} m/s[/]"

        pitch_deg = math.degrees(telem.theta)
        pitch_color = "green" if abs(pitch_deg) <= 8.0 else "red"
        pitch_str = f"[{pitch_color}]{pitch_deg:+.1f}°[/]"

        # Fuel percentage
        fuel_pct = (telem.fuel / self.vehicle.fuel_capacity) * 100.0
        fuel_color = (
            "green" if fuel_pct > 25.0 else ("yellow" if fuel_pct > 10.0 else "red")
        )

        telemetry_table.add_row(
            f"Altitude AGL:    {alt_str}",
            f"Vertical Speed:  {vy_str}",
            f"Throttle:        [cyan]{telem.throttle * 100:3.0f}%[/]",
        )
        telemetry_table.add_row(
            f"Suicide Burn Alt:{burn_str} ({burn_alert})",
            f"Horizontal Drift:{vx_str}",
            f"Engine Gimbal:   [cyan]{telem.gimbal_deg:+.1f}°[/]",
        )
        telemetry_table.add_row(
            f"Pad Offset X:    [white]{telem.x:+.1f} m[/] / ±{self.env.pad_width / 2:.0f}m",
            f"Vehicle Pitch:   {pitch_str}",
            f"Propellant:      [{fuel_color}]{telem.fuel:6.0f} kg ({fuel_pct:4.1f}%)[/]",
        )

        # Visual Bars
        bars_table = Table.grid(expand=True, padding=(0, 2))
        bars_table.add_column(ratio=1)
        bars_table.add_column(ratio=1)

        throttle_bar = ProgressBar(
            total=100.0, completed=telem.throttle * 100.0, width=28
        )
        fuel_bar = ProgressBar(total=100.0, completed=max(0.0, fuel_pct), width=28)

        bars_table.add_row(
            Text.assemble(("Thrust Output: ", "cyan")),
            Text.assemble(("Fuel Reserve:  ", fuel_color)),
        )
        bars_table.add_row(throttle_bar, fuel_bar)

        content = Group(
            header_table,
            Text(""),
            status_text,
            Text(""),
            telemetry_table,
            Text(""),
            bars_table,
        )

        return Panel(
            content,
            title="[bold cyan]SPACE-SUITE :: STARSHIP & LANDER SUICIDE BURN GNC SIMULATOR[/]",
            subtitle="[dim]Press Ctrl+C to abort simulation[/]",
            border_style="cyan",
        )
