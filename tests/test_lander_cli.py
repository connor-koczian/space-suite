"""Unit tests for the lander CLI runner and argument parser."""

import pytest

from space_suite.lander.models import (
    APOLLO_LUNAR_MODULE,
    EARTH,
    FALCON_9_BOOSTER,
    MOON,
    STARSHIP_SUPER_HEAVY,
)
from space_suite.lander.sim import get_vehicle_and_env, parse_args, run_terminal_mode


def test_cli_parse_defaults() -> None:
    args = parse_args([])
    assert args.vehicle == "starship"
    assert args.env == "earth"
    assert not args.web
    assert not args.terminal
    assert not args.manual
    assert args.port == 8057


def test_cli_parse_custom_flags() -> None:
    args = parse_args(["--web", "--port", "9090", "-v", "falcon9", "--manual"])
    assert args.web
    assert args.port == 9090
    assert args.vehicle == "falcon9"
    assert args.manual


def test_get_vehicle_and_env_mapping() -> None:
    v, e = get_vehicle_and_env("starship", "earth")
    assert v == STARSHIP_SUPER_HEAVY
    assert e == EARTH

    v_f9, e_f9 = get_vehicle_and_env("falcon9", "earth")
    assert v_f9 == FALCON_9_BOOSTER
    assert e_f9 == EARTH

    v_moon, e_moon = get_vehicle_and_env("lunar", "moon")
    assert v_moon == APOLLO_LUNAR_MODULE
    assert e_moon == MOON

    # Lunar module defaults to Moon even if earth is passed as env default
    v_lunar_def, e_lunar_def = get_vehicle_and_env("lunar", "earth")
    assert v_lunar_def == APOLLO_LUNAR_MODULE
    assert e_lunar_def == MOON


def test_run_terminal_mode_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify terminal execution runs through to touchdown instantaneously when sleep is bypassed."""
    monkeypatch.setattr("time.sleep", lambda _: None)
    result = run_terminal_mode(APOLLO_LUNAR_MODULE, MOON, autopilot_on=True)
    assert result == 0
