"""Unit tests for the autonomous suicide burn and hoverslam guidance autopilot."""

import math

from space_suite.lander.autopilot import SuicideBurnAutopilot
from space_suite.lander.models import (
    APOLLO_LUNAR_MODULE,
    EARTH,
    FALCON_9_BOOSTER,
    MOON,
    STARSHIP_SUPER_HEAVY,
    FlightStatus,
    FlightTelemetry,
)
from space_suite.lander.physics import LanderPhysicsEngine


def test_autopilot_idle_above_burn_altitude() -> None:
    """Autopilot keeps throttle at 0% when far above suicide burn threshold."""
    physics = LanderPhysicsEngine(vehicle=STARSHIP_SUPER_HEAVY, env=EARTH)
    autopilot = SuicideBurnAutopilot(physics)

    high_telem = FlightTelemetry(
        y=2000.0,
        vy=-30.0,
        theta=0.0,
        fuel=25000.0,
    )

    cmd = autopilot.compute(high_telem)
    assert cmd.throttle == 0.0
    assert not cmd.burn_active


def test_autopilot_ignition_at_burn_boundary() -> None:
    """Autopilot triggers engine burn when entering the suicide burn envelope."""
    physics = LanderPhysicsEngine(vehicle=STARSHIP_SUPER_HEAVY, env=EARTH)
    autopilot = SuicideBurnAutopilot(physics)

    y_burn = physics.calculate_suicide_burn_altitude(
        FlightTelemetry(y=100.0, vy=-80.0, fuel=20000.0)
    )

    # Place vehicle right at or just below calculated burn altitude
    burn_telem = FlightTelemetry(
        y=y_burn * 0.98,
        vy=-80.0,
        theta=0.0,
        fuel=20000.0,
    )

    cmd = autopilot.compute(burn_telem)
    assert cmd.burn_active
    assert cmd.throttle >= STARSHIP_SUPER_HEAVY.min_throttle


def test_autopilot_full_simulation_earth_starship() -> None:
    """Simulates a complete descent of Starship on Earth from 800m to touchdown."""
    physics = LanderPhysicsEngine(vehicle=STARSHIP_SUPER_HEAVY, env=EARTH)
    autopilot = SuicideBurnAutopilot(physics)

    telem = FlightTelemetry(
        y=800.0,
        vy=-70.0,
        vx=2.0,
        x=15.0,  # 15 meters offset from pad
        theta=math.radians(2.0),
        fuel=30000.0,
        autopilot_enabled=True,
    )

    dt = 0.02
    max_steps = 2000  # Up to 40 seconds of flight
    for _ in range(max_steps):
        if telem.is_touchdown:
            break
        cmd = autopilot.compute(telem)
        telem.throttle = cmd.throttle
        telem.gimbal_deg = cmd.gimbal_deg
        telem.rcs_command = cmd.rcs_command
        telem = physics.step(telem, dt=dt)

    assert telem.status == FlightStatus.LANDED
    assert telem.y == 0.0
    # Final tilt must be within safe landing margin
    assert math.degrees(abs(telem.theta)) <= 8.0
    # Landing pad crossrange must be on the deck
    assert abs(telem.x) <= EARTH.pad_width / 2.0


def test_autopilot_full_simulation_moon_lander() -> None:
    """Simulates a complete lunar landing from 600m in Moon vacuum."""
    physics = LanderPhysicsEngine(vehicle=APOLLO_LUNAR_MODULE, env=MOON)
    autopilot = SuicideBurnAutopilot(physics)

    telem = FlightTelemetry(
        y=600.0,
        vy=-40.0,
        vx=-1.5,
        x=-10.0,
        theta=math.radians(-1.5),
        fuel=5000.0,
        autopilot_enabled=True,
    )

    dt = 0.02
    max_steps = 3000
    for _ in range(max_steps):
        if telem.is_touchdown:
            break
        cmd = autopilot.compute(telem)
        telem.throttle = cmd.throttle
        telem.gimbal_deg = cmd.gimbal_deg
        telem.rcs_command = cmd.rcs_command
        telem = physics.step(telem, dt=dt)

    assert telem.status == FlightStatus.LANDED
    assert telem.y == 0.0
    assert abs(telem.x) <= MOON.pad_width / 2.0


def test_autopilot_full_simulation_falcon9() -> None:
    """Simulates Falcon 9 booster propulsive return from 1000m altitude."""
    physics = LanderPhysicsEngine(vehicle=FALCON_9_BOOSTER, env=EARTH)
    autopilot = SuicideBurnAutopilot(physics)

    telem = FlightTelemetry(
        y=1000.0,
        vy=-85.0,
        vx=0.5,
        x=5.0,
        theta=0.0,
        fuel=18000.0,
        autopilot_enabled=True,
    )

    dt = 0.02
    max_steps = 3000
    for _ in range(max_steps):
        if telem.is_touchdown:
            break
        cmd = autopilot.compute(telem)
        telem.throttle = cmd.throttle
        telem.gimbal_deg = cmd.gimbal_deg
        telem.rcs_command = cmd.rcs_command
        telem = physics.step(telem, dt=dt)

    assert telem.status == FlightStatus.LANDED
