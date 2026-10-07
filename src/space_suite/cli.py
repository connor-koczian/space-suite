"""Top-level SpaceSuite command-line interface."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from space_suite.iss import tracker


def show_suite_menu(console: Console) -> None:
    text = Text()
    text.append("🚀 SPACESUITE — ASTRONAUTICS & ROCKETRY TOOLKIT\n\n", style="bold cyan")
    text.append("Available Mission Modules:\n", style="bold white")
    text.append("  1. iss       ", style="bold green")
    text.append("— Live ISS Tracker, 3D Relative Geometry & Ubuntu Alert\n")
    text.append("                 [dim cyan](Use --web for interactive browser map & HUD!)[/]\n")
    text.append("  2. launch    ", style="bold yellow")
    text.append("— SpaceX & Rocket Mission Control Countdown (Module 2)\n")
    text.append("  3. lander    ", style="bold magenta")
    text.append("— Starship / Lunar Hoverslam Suicide Burn Simulator (Module 3)\n\n")
    text.append("Run 'iss-tracker --web' to launch the browser map dashboard.", style="cyan")

    console.print(Panel(text, border_style="cyan"))


def main(argv: list[str] | None = None) -> int:
    console = Console()
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        show_suite_menu(console)
        return 0

    subcommand = args[0]
    subargs = args[1:]

    if subcommand == "iss":
        return tracker.main(subargs)
    elif subcommand == "launch":
        console.print("[yellow]Module 2 (SpaceX & Launch Mission Control) scheduled next on roadmap.[/]")
        return 0
    elif subcommand == "lander":
        console.print("[yellow]Module 3 (Starship Suicide Burn Simulator) scheduled on roadmap.[/]")
        return 0
    else:
        console.print(f"[bold red]Unknown module:[/] '{subcommand}'. Choose 'iss', 'launch', or 'lander'.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
