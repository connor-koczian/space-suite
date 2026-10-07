"""Physics engine for the 2D Starship / Lunar Lander simulation."""

from __future__ import annotations

import math

from space_suite.lander.models import (
    EARTH,
    STARSHIP_SUPER_HEAVY,
    FlightStatus,
    FlightTelemetry,
    PlanetaryEnvironment,
    VehicleConfig,
)

STANDARD_GRAVITY = 9.80665  # m/s^2 (g_0 for Isp conversions)


class LanderPhysicsEngine:
    """High-precision 2D rigid-body rocket descent dynamics engine."""

    def __init__(
        self,
        vehicle: VehicleConfig = STARSHIP_SUPER_HEAVY,
        env: PlanetaryEnvironment = EARTH,
    ) -> None:
        self.vehicle = vehicle
        self.env = env

    def air_density_at(self, altitude: float) -> float:
        """Atmospheric density at given altitude using exponential barometric model."""
        if not self.env.has_atmosphere or altitude < 0.0:
            return 0.0
        return self.env.sea_level_air_density * math.exp(
            -altitude / self.env.scale_height
        )

    def calculate_suicide_burn_altitude(
        self, telemetry: FlightTelemetry, throttle_plan: float = 0.78
    ) -> float:
        """Calculates the exact altitude at which thrust must ignite to stop at y=0.

        Accounting for free-fall energy prior to ignition:
            Total descent mechanical energy: 2*E = v_y^2 + 2*g*y
            Planned deceleration capacity: a_plan = (throttle_plan * T_max * cos(theta)) / m
            Ignition altitude: y_burn = (v_y^2 + 2*g*y) / (2 * a_plan)
        """
        if telemetry.vy >= 0.0:
            return 0.0  # Vehicle is moving upwards, no burn required to arrest descent

        current_mass = self.vehicle.dry_mass + max(0.0, telemetry.fuel)
        a_plan = (
            throttle_plan * self.vehicle.max_thrust * math.cos(telemetry.theta)
        ) / current_mass

        if a_plan <= self.env.gravity:
            # Thrust-to-Weight Ratio is below 1.0! Rocket cannot stop before impact.
            return float("inf")

        total_energy = (telemetry.vy**2) + (
            2.0 * self.env.gravity * max(0.0, telemetry.y)
        )
        burn_altitude = total_energy / (2.0 * a_plan)
        return burn_altitude

    def step(self, telemetry: FlightTelemetry, dt: float = 0.02) -> FlightTelemetry:
        """Advance the physics simulation forward by dt seconds."""
        if telemetry.is_touchdown:
            return telemetry

        # 1. Mass calculation
        current_mass = self.vehicle.dry_mass + max(0.0, telemetry.fuel)

        # 2. Engine Thrust & Fuel Consumption
        cmd_throttle = max(0.0, min(1.0, telemetry.throttle))
        actual_thrust = 0.0
        fuel_flow_rate = 0.0

        if telemetry.fuel > 0.0 and cmd_throttle > 0.01:
            # Clamp throttle to vehicle minimum deep-throttling limit
            effective_throttle = max(self.vehicle.min_throttle, cmd_throttle)
            actual_thrust = effective_throttle * self.vehicle.max_thrust
            # Fuel flow rate: m_dot = Thrust / (Isp * g0)
            fuel_flow_rate = actual_thrust / (self.vehicle.isp * STANDARD_GRAVITY)

        fuel_consumed = fuel_flow_rate * dt
        new_fuel = max(0.0, telemetry.fuel - fuel_consumed)

        # 3. Thrust Vector Components in world coordinates
        # Gimbal angle clamped to vehicle design limit
        gimbal_clamped = max(
            -self.vehicle.max_gimbal_deg,
            min(self.vehicle.max_gimbal_deg, telemetry.gimbal_deg),
        )
        thrust_angle_rad = telemetry.theta + math.radians(gimbal_clamped)

        # Vector pointing upwards along nozzle towards vehicle nose
        thrust_fx = actual_thrust * math.sin(thrust_angle_rad)
        thrust_fy = actual_thrust * math.cos(thrust_angle_rad)

        # 4. Aerodynamic Drag
        air_density = self.air_density_at(telemetry.y)
        speed = math.hypot(telemetry.vx, telemetry.vy)
        drag_fx = 0.0
        drag_fy = 0.0

        if air_density > 0.0 and speed > 0.1:
            q_dynamic = 0.5 * air_density * (speed**2)
            drag_magnitude = (
                q_dynamic
                * self.vehicle.drag_coefficient
                * self.vehicle.cross_section_area
            )
            drag_fx = -drag_magnitude * (telemetry.vx / speed)
            drag_fy = -drag_magnitude * (telemetry.vy / speed)

        # 5. Net Linear Accelerations (Newton's 2nd Law F = m * a)
        ax = (thrust_fx + drag_fx) / current_mass
        ay = ((thrust_fy + drag_fy) / current_mass) - self.env.gravity

        # 6. Rotational Dynamics (Torque & Angular Acceleration)
        # Lever arm from center of mass to gimbal at base is half the vehicle height
        r_gimbal = self.vehicle.height * 0.48
        torque_gimbal = (
            -actual_thrust * math.sin(math.radians(gimbal_clamped)) * r_gimbal
        )

        # RCS torque
        rcs_cmd = max(-1.0, min(1.0, telemetry.rcs_command))
        r_rcs = self.vehicle.height * 0.45
        torque_rcs = rcs_cmd * self.vehicle.rcs_thrust * r_rcs

        # Aerodynamic stabilizing moment from grid fins/body
        torque_aero = 0.0
        if air_density > 0.0 and speed > 1.0:
            # Grid fins provide restoring torque towards velocity vector
            torque_aero = (
                -0.5
                * air_density
                * speed
                * self.vehicle.cross_section_area
                * telemetry.theta
                * 150.0
            )

        total_torque = torque_gimbal + torque_rcs + torque_aero
        inertia = (1.0 / 12.0) * current_mass * (self.vehicle.height**2)
        alpha = total_torque / max(100.0, inertia)

        # 7. Symplectic Euler Integration
        new_omega = telemetry.omega + (alpha * dt)
        new_theta = telemetry.theta + (new_omega * dt)

        new_vx = telemetry.vx + (ax * dt)
        new_vy = telemetry.vy + (ay * dt)

        new_x = telemetry.x + (new_vx * dt)
        new_y = telemetry.y + (new_vy * dt)
        new_time = telemetry.time + dt

        # Deploy landing legs automatically under 60 meters
        legs_deployed = telemetry.legs_deployed or (new_y < 60.0)

        # 8. Record trajectory history snapshot every 5 frames
        new_history = list(telemetry.trajectory_history)
        if len(new_history) == 0 or abs(new_history[-1][1] - new_y) > 2.0:
            new_history.append((new_x, new_y))
            if len(new_history) > 300:
                new_history.pop(0)

        # 9. Touchdown & Ground Impact Evaluation
        new_status = (
            FlightStatus.BURNING if actual_thrust > 0.0 else FlightStatus.DESCENT
        )
        new_detail = telemetry.status_detail

        if new_y <= 0.0:
            new_y = 0.0
            # Evaluate landing tolerances:
            # 1. Vertical speed <= 4.0 m/s
            # 2. Horizontal speed <= 1.8 m/s
            # 3. Vehicle tilt <= 8 degrees
            # 4. Touchdown within pad boundary
            v_vert_impact = abs(new_vy)
            v_horiz_impact = abs(new_vx)
            tilt_deg = math.degrees(abs(new_theta))
            pad_radius = self.env.pad_width / 2.0
            on_pad = abs(new_x) <= pad_radius

            soft_touchdown = (
                v_vert_impact <= 4.0
                and v_horiz_impact <= 2.2
                and tilt_deg <= 8.0
                and on_pad
            )

            if soft_touchdown:
                new_status = FlightStatus.LANDED
                new_detail = (
                    f"TOUCHDOWN CONFIRMED! V_vert={v_vert_impact:.1f} m/s, "
                    f"V_horiz={v_horiz_impact:.1f} m/s, Tilt={tilt_deg:.1f}°, Pad Offset={new_x:.1f}m"
                )
            else:
                new_status = FlightStatus.CRASHED
                failure_reasons = []
                if v_vert_impact > 4.0:
                    failure_reasons.append(
                        f"Hard impact ({v_vert_impact:.1f} m/s > 4.0 m/s)"
                    )
                if v_horiz_impact > 2.2:
                    failure_reasons.append(
                        f"Excess horizontal shear ({v_horiz_impact:.1f} m/s > 2.2 m/s)"
                    )
                if tilt_deg > 8.0:
                    failure_reasons.append(f"Severe tipover ({tilt_deg:.1f}° > 8.0°)")
                if not on_pad:
                    failure_reasons.append(
                        f"Missed landing pad ({abs(new_x):.1f}m > {pad_radius:.1f}m)"
                    )
                new_detail = "RUD / CRASH! " + ", ".join(failure_reasons)

            # Bring velocities to zero upon rest
            new_vx = 0.0
            new_vy = 0.0
            new_omega = 0.0

        return FlightTelemetry(
            time=new_time,
            x=new_x,
            y=new_y,
            vx=new_vx,
            vy=new_vy,
            theta=new_theta,
            omega=new_omega,
            fuel=new_fuel,
            throttle=telemetry.throttle,
            gimbal_deg=gimbal_clamped,
            rcs_command=telemetry.rcs_command,
            legs_deployed=legs_deployed,
            autopilot_enabled=telemetry.autopilot_enabled,
            status=new_status,
            status_detail=new_detail,
            trajectory_history=new_history,
        )
