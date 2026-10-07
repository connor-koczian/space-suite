"""Unit tests for the SpaceSuite lander physics engine."""

import math

from space_suite.lander.models import (
    EARTH,
    MOON,
    STARSHIP_SUPER_HEAVY,
    FlightStatus,
    FlightTelemetry,
)
from space_suite.lander.physics import LanderPhysicsEngine


def test_gravity_free_fall() -> None:
    """In vacuum without thrust, vertical acceleration equals -g."""
    engine = LanderPhysicsEngine(vehicle=STARSHIP_SUPER_HEAVY, env=MOON)
    initial_telem = FlightTelemetry(y=500.0, vy=0.0, throttle=0.0, fuel=1000.0)

    dt = 0.1
    next_telem = engine.step(initial_telem, dt=dt)

    expected_vy = -MOON.gravity * dt
    assert math.isclose(next_telem.vy, expected_vy, abs_tol=1e-3)
    assert next_telem.y < 500.0


def test_thrust_acceleration_and_fuel_burn() -> None:
    """Full engine throttle increases vy and depletes fuel at expected rate."""
    engine = LanderPhysicsEngine(vehicle=STARSHIP_SUPER_HEAVY, env=EARTH)
    initial_fuel = 20_000.0
    initial_telem = FlightTelemetry(
        y=500.0,
        vy=-20.0,
        throttle=1.0,
        fuel=initial_fuel,
    )

    dt = 0.1
    next_telem = engine.step(initial_telem, dt=dt)

    # Rocket should consume fuel
    assert next_telem.fuel < initial_fuel
    # Thrust-to-weight ratio for Starship is > 1.0, so vy must become less negative (decelerating)
    assert next_telem.vy > initial_telem.vy


def test_suicide_burn_altitude_calculation() -> None:
    """Calculated suicide burn altitude matches physical orbital energy equation."""
    engine = LanderPhysicsEngine(vehicle=STARSHIP_SUPER_HEAVY, env=EARTH)
    telem = FlightTelemetry(y=1000.0, vy=-60.0, fuel=20000.0)

    burn_alt = engine.calculate_suicide_burn_altitude(telem, throttle_plan=0.78)

    # Specific mechanical descent energy: 2*E = vy^2 + 2*g*y
    total_mass = STARSHIP_SUPER_HEAVY.dry_mass + telem.fuel
    a_plan = (0.78 * STARSHIP_SUPER_HEAVY.max_thrust) / total_mass
    expected_burn_alt = ((60.0**2) + (2.0 * EARTH.gravity * 1000.0)) / (2.0 * a_plan)

    assert math.isclose(burn_alt, expected_burn_alt, rel_tol=1e-3)


def test_touchdown_evaluation_soft_landing() -> None:
    """Gentle descent within flight envelope confirms successful landing."""
    engine = LanderPhysicsEngine(vehicle=STARSHIP_SUPER_HEAVY, env=EARTH)
    landing_telem = FlightTelemetry(
        y=0.05,
        vy=-1.8,
        vx=0.2,
        theta=math.radians(1.2),
        x=2.5,
        fuel=5000.0,
    )

    result = engine.step(landing_telem, dt=0.05)

    assert result.status == FlightStatus.LANDED
    assert "TOUCHDOWN CONFIRMED" in result.status_detail


def test_touchdown_evaluation_crash_hard_impact() -> None:
    """Descent at excessive vertical velocity triggers crash detection."""
    engine = LanderPhysicsEngine(vehicle=STARSHIP_SUPER_HEAVY, env=EARTH)
    crash_telem = FlightTelemetry(
        y=0.05,
        vy=-18.5,  # 18.5 m/s is destructive impact
        vx=0.0,
        theta=0.0,
        x=0.0,
    )

    result = engine.step(crash_telem, dt=0.05)

    assert result.status == FlightStatus.CRASHED
    assert "Hard impact" in result.status_detail


def test_touchdown_evaluation_crash_tipover() -> None:
    """Landing with excessive tilt triggers vehicle tipover crash."""
    engine = LanderPhysicsEngine(vehicle=STARSHIP_SUPER_HEAVY, env=EARTH)
    tilt_telem = FlightTelemetry(
        y=0.05,
        vy=-1.5,
        theta=math.radians(25.0),  # 25 degrees tilt
        x=0.0,
    )

    result = engine.step(tilt_telem, dt=0.05)

    assert result.status == FlightStatus.CRASHED
    assert "tipover" in result.status_detail.lower()
