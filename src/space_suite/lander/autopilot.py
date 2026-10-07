"""Autonomous Suicide Burn (Hoverslam) Guidance and Control Autopilot."""

from __future__ import annotations

import math
from dataclasses import dataclass

from space_suite.lander.models import FlightTelemetry
from space_suite.lander.physics import LanderPhysicsEngine


@dataclass
class AutopilotCommands:
    """Guidance actuation commands produced by the autopilot."""

    throttle: float  # [0.0, 1.0]
    gimbal_deg: float  # [-max_gimbal, +max_gimbal]
    rcs_command: float  # [-1.0, +1.0]
    burn_active: bool
    burn_altitude: float
    time_to_impact: float


class SuicideBurnAutopilot:
    """Real-time guidance, navigation & control (GNC) flight computer.

    Mimics SpaceX Starship / Falcon 9 autonomous landing flight software:
    - Free-fall coast phase with aerodynamic/RCS attitude orientation.
    - Precision calculation of suicide burn ignition boundary using specific orbital energy.
    - Closed-loop throttle modulation to nullify velocity at altitude 0.
    - Terminal upright alignment (theta -> 0) and crossrange pin-pointing on the landing pad.
    """

    def __init__(self, physics: LanderPhysicsEngine) -> None:
        self.physics = physics
        self.vehicle = physics.vehicle
        self.env = physics.env
        self._burn_started = False

    def reset(self) -> None:
        """Reset autopilot internal state."""
        self._burn_started = False

    def compute(self, telem: FlightTelemetry) -> AutopilotCommands:
        """Compute the next actuation command for the vehicle."""
        if telem.is_touchdown:
            return AutopilotCommands(
                throttle=0.0,
                gimbal_deg=0.0,
                rcs_command=0.0,
                burn_active=False,
                burn_altitude=0.0,
                time_to_impact=0.0,
            )

        current_mass = self.vehicle.dry_mass + max(0.0, telem.fuel)
        y_burn = self.physics.calculate_suicide_burn_altitude(telem, throttle_plan=0.78)

        # Estimate time to impact
        time_to_impact = abs(telem.y / telem.vy) if telem.vy < -0.1 else 999.0

        # Trigger suicide burn if current altitude is within the calculated ignition curve
        if telem.y <= y_burn or self._burn_started:
            self._burn_started = True

        # --- 1. Vertical Throttle Control ---
        cmd_throttle = 0.0
        if self._burn_started:
            if telem.vy >= -0.3 and telem.y < 35.0:
                # Anti-overshoot cutoff: rocket has arrested descent near ground;
                # cut throttle immediately to prevent launching back into the sky
                cmd_throttle = 0.0
            elif telem.y > 18.0:
                # Dynamic energy-matching deceleration requirement:
                # v^2 = 2 * a_req * y  => a_req = g + (v_y^2 - v_touchdown^2) / (2 * y)
                v_target_touchdown = -1.8  # Target gentle velocity at contact
                a_req = self.env.gravity + (
                    (telem.vy**2 - v_target_touchdown**2) / (2.0 * max(2.0, telem.y))
                )
                t_req = current_mass * a_req / max(0.4, math.cos(telem.theta))
                raw_throttle = t_req / self.vehicle.max_thrust
                cmd_throttle = max(self.vehicle.min_throttle, min(1.0, raw_throttle))
            else:
                # Terminal descent (< 18 meters): Precision velocity servo to -1.5 m/s
                target_vy = -1.5
                vy_error = target_vy - telem.vy
                # Hover thrust required to balance gravity
                t_hover = current_mass * self.env.gravity
                t_servo = t_hover + (vy_error * current_mass * 2.2)
                raw_throttle = t_servo / self.vehicle.max_thrust
                cmd_throttle = max(self.vehicle.min_throttle, min(1.0, raw_throttle))

        # --- 2. Horizontal Guidance & Crossrange Target ---
        # Steer vehicle crossrange towards pad center (x = 0) while preventing lateral drift
        target_vx = max(-1.8, min(1.8, -0.15 * telem.x))
        vx_err = telem.vx - target_vx
        if telem.y > 6.0:
            max_allowed_tilt = math.radians(3.5)
            desired_tilt = max(-max_allowed_tilt, min(max_allowed_tilt, -0.05 * vx_err))
        else:
            # Final 6 meters: align perfectly perpendicular to ground for touchdown
            desired_tilt = 0.0

        # --- 3. Attitude & Gimbal Servo Control (PD Loop) ---
        theta_err = telem.theta - desired_tilt
        kp_gimbal = 2.5
        kd_gimbal = 3.5
        cmd_gimbal = (kp_gimbal * math.degrees(theta_err)) + (
            kd_gimbal * math.degrees(telem.omega)
        )
        cmd_gimbal = max(
            -self.vehicle.max_gimbal_deg, min(self.vehicle.max_gimbal_deg, cmd_gimbal)
        )

        # RCS Thrusters assist attitude control
        kp_rcs = 2.5
        kd_rcs = 4.0
        cmd_rcs = -(kp_rcs * theta_err) - (kd_rcs * telem.omega)
        cmd_rcs = max(-1.0, min(1.0, cmd_rcs))

        return AutopilotCommands(
            throttle=cmd_throttle,
            gimbal_deg=cmd_gimbal,
            rcs_command=cmd_rcs,
            burn_active=self._burn_started,
            burn_altitude=y_burn,
            time_to_impact=time_to_impact,
        )
