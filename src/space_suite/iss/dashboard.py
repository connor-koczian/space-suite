"""Rich terminal dashboard for live ISS tracking and telemetry."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from rich.align import Align
from rich.box import ROUNDED, SIMPLE
from rich.console import RenderableType
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from space_suite.iss.models import ISSTelemetry, ObserverCoords, RelativePosition
from space_suite.iss.orbital_math import calculate_orbital_period_minutes


class ISSDashboard:
    """Renders real-time ISS telemetry and relative ground geometry using Rich."""

    def __init__(
        self,
        observer: ObserverCoords,
        threshold_km: float = 1000.0,
        history_len: int = 8,
    ) -> None:
        self.observer = observer
        self.threshold_km = threshold_km
        self.history: deque[dict[str, str]] = deque(maxlen=history_len)
        self.last_distance: float | None = None
        self.min_distance_seen: float | None = None

    def record_history(self, iss: ISSTelemetry, rel: RelativePosition) -> None:
        """Record a telemetry snapshot into the historical trail."""
        trend = "—"
        if self.last_distance is not None:
            delta = rel.ground_distance_km - self.last_distance
            if delta < -0.5:
                trend = "▼ Approaching"
            elif delta > 0.5:
                trend = "▲ Receding"
            else:
                trend = "● Steady"

        self.last_distance = rel.ground_distance_km
        if self.min_distance_seen is None or rel.ground_distance_km < self.min_distance_seen:
            self.min_distance_seen = rel.ground_distance_km

        self.history.append({
            "time": iss.time_utc.strftime("%H:%M:%S"),
            "lat": iss.lat_str,
            "lon": iss.lon_str,
            "alt": f"{iss.altitude_km:.1f} km",
            "dist": f"{rel.ground_distance_km:,.1f} km",
            "el": f"{rel.elevation_deg:+.1f}°",
            "trend": trend,
            "vis": "☀️ Day" if iss.is_sunlit else "🌑 Dark",
        })

    def render(
        self,
        iss: ISSTelemetry | None,
        rel: RelativePosition | None,
        error_msg: str | None = None,
        poll_interval: float = 2.0,
        notifier_active: bool = True,
    ) -> RenderableType:
        """Construct the complete Rich dashboard renderable."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="main", size=15),
            Layout(name="history", size=10),
            Layout(name="footer", size=3),
        )

        layout["header"].update(self._render_header(iss))
        layout["main"].update(self._render_main(iss, rel, error_msg))
        layout["history"].update(self._render_history())
        layout["footer"].update(self._render_footer(poll_interval, notifier_active))

        return layout

    def _render_header(self, iss: ISSTelemetry | None) -> Panel:
        """Render top mission control banner."""
        title_text = Text()
        title_text.append("🛰️  INTERNATIONAL SPACE STATION ", style="bold cyan")
        title_text.append("• MISSION CONTROL TELEMETRY", style="bold white")

        now_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        status_text = Text(f"GROUND STATION: {self.observer.name} | SYSTEM CLOCK: {now_utc}", style="dim")

        header_table = Table.grid(expand=True)
        header_table.add_column(justify="left")
        header_table.add_column(justify="right")
        header_table.add_row(title_text, status_text)

        return Panel(
            header_table,
            border_style="cyan",
            box=ROUNDED,
        )

    def _render_main(
        self,
        iss: ISSTelemetry | None,
        rel: RelativePosition | None,
        error_msg: str | None,
    ) -> Layout:
        """Render middle split panels: Orbital Telemetry and Ground Geometry."""
        main_layout = Layout()
        main_layout.split_row(
            Layout(name="orbital", ratio=1),
            Layout(name="ground", ratio=1),
        )

        if error_msg:
            error_panel = Panel(
                Align.center(f"[bold red]⚠️ Telemetry Signal Interrupted[/]\n\n[yellow]{error_msg}[/]"),
                title="Telemetry Link Error",
                border_style="red",
                box=ROUNDED,
            )
            main_layout["orbital"].update(error_panel)
            main_layout["ground"].update(error_panel)
            return main_layout

        if not iss or not rel:
            loading_panel = Panel(
                Align.center("[yellow]Acquiring telemetry downlink...[/]"),
                box=ROUNDED,
            )
            main_layout["orbital"].update(loading_panel)
            main_layout["ground"].update(loading_panel)
            return main_layout

        main_layout["orbital"].update(self._render_orbital_panel(iss))
        main_layout["ground"].update(self._render_ground_panel(rel, iss))
        return main_layout

    def _render_orbital_panel(self, iss: ISSTelemetry) -> Panel:
        """Render ISS orbital mechanics telemetry."""
        table = Table(box=SIMPLE, expand=True, show_header=False)
        table.add_column("Property", style="cyan", width=22)
        table.add_column("Value", style="bold white")

        table.add_row("Sub-Satellite Latitude", iss.lat_str)
        table.add_row("Sub-Satellite Longitude", iss.lon_str)
        table.add_row("Orbital Altitude", f"{iss.altitude_km:.2f} km ({iss.altitude_km * 0.621371:.1f} mi)")
        table.add_row(
            "Orbital Velocity",
            f"{iss.velocity_kmh:,.1f} km/h [dim]({iss.velocity_kms:.2f} km/s)[/]",
        )
        mach = iss.velocity_kmh / 1234.8
        table.add_row("Equivalent Mach", f"Mach {mach:.1f}")

        period_min = calculate_orbital_period_minutes(iss.altitude_km)
        laps_day = 1440.0 / period_min
        table.add_row(
            "Orbital Period (T)",
            f"{period_min:.2f} min [dim]({laps_day:.1f} orbits/day)[/]",
        )

        sunlight_badge = (
            "[bold yellow]☀️ SUNLIT (DAYLIGHT)[/]"
            if iss.is_sunlit
            else "[bold blue]🌑 ECLIPSED (EARTH SHADOW)[/]"
        )
        table.add_row("Solar Illumination", sunlight_badge)
        table.add_row("Horizon Footprint", f"⌀ {iss.footprint_km:,.1f} km")

        return Panel(
            table,
            title="[bold green]● Orbital Telemetry (ISS NORAD #25544)[/]",
            border_style="green",
            box=ROUNDED,
        )

    def _render_ground_panel(self, rel: RelativePosition, iss: ISSTelemetry) -> Panel:
        """Render observer-relative distance, elevation and pass alert status."""
        table = Table(box=SIMPLE, expand=True, show_header=False)
        table.add_column("Parameter", style="cyan", width=24)
        table.add_column("Value", style="bold white")

        table.add_row("Observer Coordinates", f"{self.observer.lat_str}, {self.observer.lon_str}")
        table.add_row(
            "Surface Distance",
            f"{rel.ground_distance_km:,.1f} km [dim]({rel.ground_distance_miles:,.1f} mi)[/]",
        )
        table.add_row(
            "Slant Range (Direct 3D)",
            f"{rel.slant_range_km:,.1f} km [dim]({rel.slant_range_miles:,.1f} mi)[/]",
        )

        # Elevation badge
        if rel.elevation_deg >= 10.0:
            el_style = "bold green"
            horizon_status = "ABOVE HORIZON (LINE OF SIGHT)"
        elif rel.elevation_deg > 0.0:
            el_style = "green"
            horizon_status = "LOW ON HORIZON"
        else:
            el_style = "dim"
            horizon_status = "BELOW HORIZON"

        table.add_row("Horizon Elevation", f"[{el_style}]{rel.elevation_deg:+.2f}° [{horizon_status}][/{el_style}]")
        table.add_row("Compass Bearing", f"{rel.bearing_deg:05.1f}° [bold magenta]{rel.compass_heading}[/]")

        # Pass status badge
        if rel.is_in_range:
            pass_status = "[bold white on red] 🛰️ OVERHEAD PASS IN RANGE! [/]"
            border_color = "red"
        else:
            pass_status = f"[dim]STANDBY (Alert threshold: ≤ {self.threshold_km:.0f} km)[/]"
            border_color = "blue"

        table.add_row("Overhead Alert Status", pass_status)
        if self.min_distance_seen is not None:
            table.add_row("Closest Approach", f"{self.min_distance_seen:,.1f} km")

        return Panel(
            table,
            title=f"[bold {border_color}]● Ground Station Relative: {self.observer.name}[/]",
            border_style=border_color,
            box=ROUNDED,
        )

    def _render_history(self) -> Panel:
        """Render recent telemetry updates in a tracking table."""
        table = Table(box=SIMPLE, expand=True)
        table.add_column("UTC Time", style="cyan", justify="center")
        table.add_column("ISS Lat", justify="right")
        table.add_column("ISS Lon", justify="right")
        table.add_column("Altitude", justify="right")
        table.add_column("Ground Dist", justify="right")
        table.add_column("Elevation", justify="right")
        table.add_column("Relative Trend", justify="center")
        table.add_column("Sunlight", justify="center")

        if not self.history:
            table.add_row("—", "—", "—", "—", "—", "—", "Awaiting telemetry samples...", "—")
        else:
            for item in reversed(self.history):
                trend_style = "bold green" if "Approaching" in item["trend"] else "dim"
                table.add_row(
                    item["time"],
                    item["lat"],
                    item["lon"],
                    item["alt"],
                    item["dist"],
                    item["el"],
                    f"[{trend_style}]{item['trend']}[/{trend_style}]",
                    item["vis"],
                )

        return Panel(
            table,
            title="[bold yellow]● Telemetry Trail (Live Polling History)[/]",
            border_style="yellow",
            box=ROUNDED,
        )

    def _render_footer(self, poll_interval: float, notifier_active: bool) -> Panel:
        """Render bottom status bar and key bindings."""
        notify_str = "[bold green]ACTIVE (notify-send ready)[/]" if notifier_active else "[yellow]DISABLED/UNAVAILABLE[/]"
        footer_text = Text.from_markup(
            f"Poll Interval: [cyan]{poll_interval:.1f}s[/] | "
            f"Desktop Alerts: {notify_str} | "
            f"Range Trigger: [cyan]≤ {self.threshold_km:,.0f} km[/] | "
            f"Press [bold red]Ctrl+C[/] to safely exit."
        )
        return Panel(
            Align.center(footer_text),
            border_style="dim",
            box=ROUNDED,
        )
