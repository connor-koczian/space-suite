"""Data models and configurations for the SpaceSuite lander simulator."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class FlightStatus(str, Enum):
    """Current mission status of the lander."""

    DESCENT = "DESCENT"
    BURNING = "BURNING"
    LANDED = "LANDED"
    CRASHED = "CRASHED"


@dataclass(frozen=True)
class VehicleConfig:
    """Aerospace specifications for a rocket vehicle."""

    name: str
    dry_mass: float  # kg (vehicle structural empty mass)
    fuel_capacity: float  # kg (maximum propellant capacity)
    max_thrust: float  # N (maximum vacuum/sea-level thrust)
    min_throttle: float  # Fraction 0.0 - 1.0 (minimum engine deep throttle limit)
    isp: float  # Seconds (specific impulse)
    height: float  # Meters
    width: float  # Meters
    max_gimbal_deg: float = 12.0  # Max thrust vector gimbal angle in degrees
    rcs_thrust: float = 8000.0  # N (attitude control reaction thruster force)
    drag_coefficient: float = 0.82  # Aerodynamic drag coefficient Cd
    cross_section_area: float = 63.6  # m^2 (frontal/side reference area for drag)

    @property
    def total_wet_mass(self) -> float:
        """Total mass with 100% fuel."""
        return self.dry_mass + self.fuel_capacity

    @property
    def mass_moment_of_inertia_empty(self) -> float:
        """Approximate mass moment of inertia I = (1/12) * m * L^2 (kg*m^2)."""
        return (1.0 / 12.0) * self.dry_mass * (self.height**2)


# Pre-configured aerospace vehicles
STARSHIP_SUPER_HEAVY = VehicleConfig(
    name="Starship Super Heavy",
    dry_mass=100_000.0,  # 100 metric tons
    fuel_capacity=80_000.0,  # 80 tons reserve for landing burn
    max_thrust=2_200_000.0 * 3,  # 3 Center landing Raptors (~6.6 MN)
    min_throttle=0.40,  # 40% deep throttle capability
    isp=330.0,
    height=50.0,
    width=9.0,
    max_gimbal_deg=15.0,
    rcs_thrust=25_000.0,
    drag_coefficient=0.85,
    cross_section_area=63.6,
)

FALCON_9_BOOSTER = VehicleConfig(
    name="Falcon 9 First Stage",
    dry_mass=25_000.0,  # 25 metric tons
    fuel_capacity=22_000.0,  # 22 tons entry & landing reserve
    max_thrust=845_000.0,  # Single Merlin 1D landing burn (~845 kN)
    min_throttle=0.57,  # Merlin 1D throttles down to ~57%
    isp=282.0,
    height=41.2,
    width=3.7,
    max_gimbal_deg=8.0,
    rcs_thrust=5_000.0,
    drag_coefficient=0.75,
    cross_section_area=10.7,
)

APOLLO_LUNAR_MODULE = VehicleConfig(
    name="Lunar Descent Module",
    dry_mass=4_700.0,  # 4.7 metric tons
    fuel_capacity=8_200.0,  # 8.2 tons hypergolic propellant
    max_thrust=45_040.0,  # Lunar Module Descent Engine (LMDE) ~45 kN
    min_throttle=0.10,  # LMDE was famously throttleable down to 10%
    isp=311.0,
    height=7.0,
    width=4.3,
    max_gimbal_deg=6.0,
    rcs_thrust=1_200.0,
    drag_coefficient=1.05,
    cross_section_area=15.0,
)


@dataclass(frozen=True)
class PlanetaryEnvironment:
    """Celestial body surface environment."""

    name: str
    gravity: float  # m/s^2
    has_atmosphere: bool
    sea_level_air_density: float = 1.225  # kg/m^3 (Earth standard)
    scale_height: float = 8500.0  # m (barometric scale height)
    pad_width: float = 35.0  # meters width of target landing pad


EARTH = PlanetaryEnvironment(
    name="Earth (Cape Canaveral / Starbase)",
    gravity=9.80665,
    has_atmosphere=True,
    sea_level_air_density=1.225,
    scale_height=8500.0,
    pad_width=40.0,
)

MOON = PlanetaryEnvironment(
    name="Moon (Ocean of Storms)",
    gravity=1.62,
    has_atmosphere=False,
    sea_level_air_density=0.0,
    scale_height=1.0,
    pad_width=50.0,
)

MARS = PlanetaryEnvironment(
    name="Mars (Jezero Crater)",
    gravity=3.72,
    has_atmosphere=True,
    sea_level_air_density=0.020,  # ~1% of Earth's atmosphere
    scale_height=11100.0,
    pad_width=45.0,
)


@dataclass
class FlightTelemetry:
    """Dynamic instantaneous snapshot of the vehicle in flight."""

    time: float = 0.0  # Elapsed mission seconds
    x: float = 0.0  # Crossrange position relative to pad center (meters)
    y: float = 1200.0  # Altitude above ground level (meters)
    vx: float = 0.0  # Horizontal velocity (m/s, positive = right)
    vy: float = -95.0  # Vertical velocity (m/s, negative = descending)
    theta: float = 0.0  # Vehicle pitch angle in radians (0 = straight up)
    omega: float = 0.0  # Angular velocity in radians/sec
    fuel: float = 15000.0  # Current propellant mass in kg
    throttle: float = 0.0  # Commanded engine throttle [0.0, 1.0]
    gimbal_deg: float = 0.0  # Commanded engine gimbal in degrees
    rcs_command: float = 0.0  # RCS command [-1.0 = left, +1.0 = right]
    legs_deployed: bool = False
    autopilot_enabled: bool = False
    status: FlightStatus = FlightStatus.DESCENT
    status_detail: str = "Free fall descent towards landing zone"

    # Historical flight trail for trajectory plotting (capped list of (x, y))
    trajectory_history: list[tuple[float, float]] = field(default_factory=list)

    @property
    def speed(self) -> float:
        """Total scalar velocity magnitude in m/s."""
        return math.hypot(self.vx, self.vy)

    @property
    def pitch_degrees(self) -> float:
        """Vehicle pitch in degrees."""
        return math.degrees(self.theta)

    @property
    def is_touchdown(self) -> bool:
        """Whether the vehicle has contacted the ground."""
        return self.status in (FlightStatus.LANDED, FlightStatus.CRASHED)
