"""Interactive 60 FPS Pygame Graphical Simulation for Starship & Lander Suicide Burn."""

from __future__ import annotations

import math
import random
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from space_suite.lander.models import PlanetaryEnvironment, VehicleConfig

import pygame

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

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768


class Particle:
    """Flame or smoke visual effect particle."""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        color: tuple[int, int, int],
        radius: float,
        lifetime: float,
    ) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.radius = radius
        self.lifetime = lifetime
        self.age = 0.0

    def update(self, dt: float) -> bool:
        """Update particle position and age. Returns False if expired."""
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt
        return self.age < self.lifetime


class LanderPygameRenderer:
    """Full-featured 2D vector graphics simulation display."""

    def __init__(
        self,
        vehicle: VehicleConfig = STARSHIP_SUPER_HEAVY,
        env: PlanetaryEnvironment = EARTH,
        initial_altitude: float = 850.0,
        initial_vy: float = -75.0,
        initial_x: float = 20.0,
        initial_vx: float = 1.5,
        start_autopilot: bool = True,
    ) -> None:
        self.vehicle = vehicle
        self.env = env
        self.initial_alt = initial_altitude
        self.initial_vy = initial_vy
        self.initial_x = initial_x
        self.initial_vx = initial_vx
        self.start_autopilot = start_autopilot

        self.physics = LanderPhysicsEngine(self.vehicle, self.env)
        self.autopilot = SuicideBurnAutopilot(self.physics)
        self.telemetry = self._create_initial_telemetry()

        self.particles: list[Particle] = []
        self.stars: list[tuple[int, int, int]] = [
            (
                random.randint(0, SCREEN_WIDTH),
                random.randint(0, SCREEN_HEIGHT - 120),
                random.randint(1, 2),
            )
            for _ in range(120)
        ]

    def _create_initial_telemetry(self) -> FlightTelemetry:
        return FlightTelemetry(
            y=self.initial_alt,
            vy=self.initial_vy,
            x=self.initial_x,
            vx=self.initial_vx,
            theta=math.radians(1.5),
            fuel=self.vehicle.fuel_capacity * 0.45,
            autopilot_enabled=self.start_autopilot,
        )

    def reset(self) -> None:
        """Reset the simulation back to initial launch conditions."""
        self.physics = LanderPhysicsEngine(self.vehicle, self.env)
        self.autopilot = SuicideBurnAutopilot(self.physics)
        self.telemetry = self._create_initial_telemetry()
        self.particles.clear()

    def set_vehicle(self, vehicle: VehicleConfig, env: PlanetaryEnvironment) -> None:
        """Switch active aerospace vehicle and environment."""
        self.vehicle = vehicle
        self.env = env
        if vehicle == APOLLO_LUNAR_MODULE:
            self.initial_alt = 600.0
            self.initial_vy = -40.0
            self.initial_x = -12.0
            self.initial_vx = -0.8
        elif vehicle == FALCON_9_BOOSTER:
            self.initial_alt = 1000.0
            self.initial_vy = -85.0
            self.initial_x = 10.0
            self.initial_vx = 0.5
        else:
            self.initial_alt = 850.0
            self.initial_vy = -75.0
            self.initial_x = 20.0
            self.initial_vx = 1.5
        self.reset()

    def run(self) -> None:
        """Main game loop for Pygame execution."""
        pygame.init()
        pygame.display.set_caption(
            f"SpaceSuite — {self.vehicle.name} Suicide Burn Simulator"
        )
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        clock = pygame.time.Clock()
        font_large = pygame.font.SysFont("monospace", 22, bold=True)
        font_med = pygame.font.SysFont("monospace", 15, bold=True)
        font_small = pygame.font.SysFont("monospace", 12)

        running = True
        while running:
            dt = clock.tick(60) / 1000.0  # Cap at 60 FPS
            dt = min(dt, 0.05)

            # 1. Event handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_r:
                        self.reset()
                    elif event.key == pygame.K_a:
                        self.telemetry.autopilot_enabled = (
                            not self.telemetry.autopilot_enabled
                        )
                        if not self.telemetry.autopilot_enabled:
                            self.autopilot.reset()
                    elif event.key == pygame.K_SPACE:
                        self.telemetry.throttle = 0.0
                    elif event.key == pygame.K_1:
                        self.set_vehicle(STARSHIP_SUPER_HEAVY, EARTH)
                    elif event.key == pygame.K_2:
                        self.set_vehicle(FALCON_9_BOOSTER, EARTH)
                    elif event.key == pygame.K_3:
                        self.set_vehicle(APOLLO_LUNAR_MODULE, MOON)

            # Manual keyboard controls (if Autopilot is OFF and vehicle airborne)
            keys = pygame.key.get_pressed()
            if not self.telemetry.autopilot_enabled and not self.telemetry.is_touchdown:
                if keys[pygame.K_UP]:
                    self.telemetry.throttle = min(
                        1.0, self.telemetry.throttle + 1.2 * dt
                    )
                elif keys[pygame.K_DOWN]:
                    self.telemetry.throttle = max(
                        0.0, self.telemetry.throttle - 1.5 * dt
                    )

                if keys[pygame.K_LEFT]:
                    self.telemetry.rcs_command = 1.0
                    self.telemetry.gimbal_deg = min(
                        self.vehicle.max_gimbal_deg,
                        self.telemetry.gimbal_deg + 25.0 * dt,
                    )
                elif keys[pygame.K_RIGHT]:
                    self.telemetry.rcs_command = -1.0
                    self.telemetry.gimbal_deg = max(
                        -self.vehicle.max_gimbal_deg,
                        self.telemetry.gimbal_deg - 25.0 * dt,
                    )
                else:
                    self.telemetry.rcs_command = 0.0
                    self.telemetry.gimbal_deg *= 0.85  # Spring back gimbal center

            # 2. Physics & Autopilot step
            burn_alt = self.physics.calculate_suicide_burn_altitude(self.telemetry)
            if self.telemetry.autopilot_enabled and not self.telemetry.is_touchdown:
                cmd = self.autopilot.compute(self.telemetry)
                self.telemetry.throttle = cmd.throttle
                self.telemetry.gimbal_deg = cmd.gimbal_deg
                self.telemetry.rcs_command = cmd.rcs_command
                burn_alt = cmd.burn_altitude

            self.telemetry = self.physics.step(self.telemetry, dt=dt)

            # 3. Particle generation
            self._update_particles(dt)

            # 4. Rendering
            self._draw_frame(screen, font_large, font_med, font_small, burn_alt)
            pygame.display.flip()

        pygame.quit()
        sys.exit(0)

    def _update_particles(self, dt: float) -> None:
        """Spawn engine exhaust and explosion particles."""
        # Active engine flame
        if (
            self.telemetry.throttle > 0.01
            and self.telemetry.fuel > 0.0
            and not self.telemetry.is_touchdown
        ):
            screen_x, screen_y = self._world_to_screen(
                self.telemetry.x, self.telemetry.y
            )
            # Base of rocket
            rocket_len_px = 75.0
            half_len = rocket_len_px / 2.0
            base_x = screen_x - half_len * math.sin(self.telemetry.theta)
            base_y = screen_y + half_len * math.cos(self.telemetry.theta)

            flame_dir_x = -math.sin(
                self.telemetry.theta + math.radians(self.telemetry.gimbal_deg)
            )
            flame_dir_y = math.cos(
                self.telemetry.theta + math.radians(self.telemetry.gimbal_deg)
            )

            for _ in range(int(8 * self.telemetry.throttle)):
                speed = random.uniform(80.0, 240.0) * self.telemetry.throttle
                spread = random.uniform(-0.25, 0.25)
                pvx = (flame_dir_x + spread) * speed
                pvy = (flame_dir_y + spread) * speed
                col = random.choice(
                    [
                        (255, 230, 100),  # Inner white/yellow core
                        (255, 140, 20),  # Orange fire
                        (255, 60, 10),  # Red edge
                        (100, 180, 255),  # Methane blue Mach diamond
                    ]
                )
                self.particles.append(
                    Particle(
                        base_x,
                        base_y,
                        pvx,
                        pvy,
                        col,
                        random.uniform(3.0, 7.0),
                        random.uniform(0.15, 0.45),
                    )
                )

        # Update and cull particles
        self.particles = [p for p in self.particles if p.update(dt)]

    def _world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        """Convert world coordinates (meters) to screen coordinates (pixels)."""
        # Dynamic camera framing: keeps ground visible and vehicle centered vertically
        ground_screen_y = SCREEN_HEIGHT - 90
        # Scale: pixels per meter (zooms in dynamically as vehicle nears ground)
        scale = (
            1.3
            if self.telemetry.y < 120.0
            else (0.8 if self.telemetry.y < 350.0 else 0.55)
        )
        center_x = SCREEN_WIDTH / 2.0

        screen_x = center_x + (x * scale)
        screen_y = ground_screen_y - (y * scale)
        return screen_x, screen_y

    def _draw_frame(
        self,
        screen: pygame.Surface,
        font_large: pygame.font.Font,
        font_med: pygame.font.Font,
        font_small: pygame.font.Font,
        burn_alt: float,
    ) -> None:
        """Render the complete graphical frame."""
        # 1. Dark Aerospace Space Background
        screen.fill((10, 14, 23))

        # Stars
        for sx, sy, srad in self.stars:
            pygame.draw.circle(screen, (180, 195, 215), (sx, sy), srad)

        # 2. Ground & Landing Pad
        ground_screen_y = SCREEN_HEIGHT - 90
        pad_center_x = SCREEN_WIDTH / 2.0
        pad_width_px = self.env.pad_width * (1.3 if self.telemetry.y < 120.0 else 0.8)

        # Terrain line
        terrain_color = (60, 65, 75) if self.env.has_atmosphere else (90, 88, 85)
        pygame.draw.rect(
            screen,
            terrain_color,
            (0, ground_screen_y, SCREEN_WIDTH, SCREEN_HEIGHT - ground_screen_y),
        )

        # Landing pad concrete foundation
        pad_rect = pygame.Rect(
            pad_center_x - (pad_width_px / 2.0),
            ground_screen_y - 8,
            pad_width_px,
            12,
        )
        pygame.draw.rect(screen, (130, 140, 155), pad_rect, border_radius=3)
        pygame.draw.rect(screen, (240, 180, 20), pad_rect, width=2, border_radius=3)

        # Pad approach lights (pulsing yellow/cyan)
        light_color = (
            (0, 255, 200) if self.telemetry.autopilot_enabled else (255, 200, 30)
        )
        pygame.draw.circle(
            screen,
            light_color,
            (int(pad_center_x - pad_width_px / 2.0 + 4), ground_screen_y - 2),
            4,
        )
        pygame.draw.circle(
            screen,
            light_color,
            (int(pad_center_x + pad_width_px / 2.0 - 4), ground_screen_y - 2),
            4,
        )
        pygame.draw.circle(
            screen, (255, 255, 255), (int(pad_center_x), ground_screen_y - 2), 3
        )

        # 3. Trajectory History Path
        if len(self.telemetry.trajectory_history) > 1:
            points = [
                self._world_to_screen(px, py)
                for px, py in self.telemetry.trajectory_history
            ]
            if len(points) >= 2:
                pygame.draw.lines(screen, (0, 180, 255), False, points, 2)

        # 4. Particles (Engine flame)
        for p in self.particles:
            alpha = max(0, min(255, int(255 * (1.0 - p.age / p.lifetime))))
            surf = pygame.Surface(
                (int(p.radius * 2), int(p.radius * 2)), pygame.SRCALPHA
            )
            pygame.draw.circle(
                surf, (*p.color, alpha), (int(p.radius), int(p.radius)), int(p.radius)
            )
            screen.blit(surf, (int(p.x - p.radius), int(p.y - p.radius)))

        # 5. Rocket Vehicle Sprite Drawing
        self._draw_vehicle(screen)

        # 6. Aerospace HUD Overlay
        self._draw_hud(screen, font_large, font_med, font_small, burn_alt)

    def _draw_vehicle(self, screen: pygame.Surface) -> None:
        """Draw the rotated vector rocket with aerodynamic flaps and landing gear."""
        screen_x, screen_y = self._world_to_screen(self.telemetry.x, self.telemetry.y)
        theta = self.telemetry.theta

        # Vehicle dimensions in pixels
        v_h = 70.0
        v_w = 14.0

        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        def transform(local_x: float, local_y: float) -> tuple[float, float]:
            """Rotate and translate local body coordinates to screen space."""
            rx = (local_x * cos_t) + (local_y * sin_t)
            ry = (-local_x * sin_t) + (local_y * cos_t)
            return screen_x + rx, screen_y + ry

        # Rocket Body Polygon (Nose cone at top, straight cylinder body)
        half_w = v_w / 2.0
        half_h = v_h / 2.0
        nose_y = -half_h - 14.0

        body_poly = [
            transform(0.0, nose_y),  # Nose tip
            transform(half_w, -half_h),  # Upper right
            transform(half_w, half_h),  # Lower right base
            transform(-half_w, half_h),  # Lower left base
            transform(-half_w, -half_h),  # Upper left
        ]

        body_color = (200, 205, 215)  # Stainless steel / White
        if self.vehicle == APOLLO_LUNAR_MODULE:
            body_color = (220, 180, 60)  # Gold Kapton foil

        pygame.draw.polygon(screen, body_color, body_poly)
        pygame.draw.polygon(screen, (50, 55, 65), body_poly, width=2)

        # Starship dark heat shield tile line (left side)
        if self.vehicle == STARSHIP_SUPER_HEAVY:
            shield_poly = [
                transform(0.0, nose_y),
                transform(-half_w, -half_h),
                transform(-half_w, half_h),
                transform(0.0, half_h),
            ]
            pygame.draw.polygon(screen, (35, 38, 45), shield_poly)

        # Aerodynamic flaps / grid fins
        if self.vehicle != APOLLO_LUNAR_MODULE:
            # Forward fins
            pygame.draw.line(
                screen,
                (80, 85, 95),
                transform(-half_w, -half_h + 8),
                transform(-half_w - 9, -half_h + 14),
                3,
            )
            pygame.draw.line(
                screen,
                (80, 85, 95),
                transform(half_w, -half_h + 8),
                transform(half_w + 9, -half_h + 14),
                3,
            )
            # Aft flaps
            pygame.draw.line(
                screen,
                (80, 85, 95),
                transform(-half_w, half_h - 18),
                transform(-half_w - 12, half_h - 4),
                3,
            )
            pygame.draw.line(
                screen,
                (80, 85, 95),
                transform(half_w, half_h - 18),
                transform(half_w + 12, half_h - 4),
                3,
            )

        # Landing Legs (Deploy if y < 60m or touchdown)
        if self.telemetry.legs_deployed:
            leg_len = 16.0
            pygame.draw.line(
                screen,
                (220, 220, 230),
                transform(-half_w, half_h),
                transform(-half_w - 12, half_h + leg_len),
                3,
            )
            pygame.draw.line(
                screen,
                (220, 220, 230),
                transform(half_w, half_h),
                transform(half_w + 12, half_h + leg_len),
                3,
            )

        # Engine Gimbal Bell at base
        gimbal_rad = math.radians(self.telemetry.gimbal_deg)
        nozzle_tip_x = -7.0 * math.sin(gimbal_rad)
        nozzle_tip_y = half_h + 7.0 * math.cos(gimbal_rad)
        pygame.draw.line(
            screen,
            (255, 120, 30) if self.telemetry.throttle > 0.01 else (100, 105, 115),
            transform(0.0, half_h),
            transform(nozzle_tip_x, nozzle_tip_y),
            4,
        )

    def _draw_hud(
        self,
        screen: pygame.Surface,
        font_large: pygame.font.Font,
        font_med: pygame.font.Font,
        font_small: pygame.font.Font,
        burn_alt: float,
    ) -> None:
        """Render high-contrast aerospace HUD overlays."""
        # Top Header Bar
        header_surf = font_large.render(
            f"🚀 {self.vehicle.name.upper()}", True, (0, 230, 255)
        )
        screen.blit(header_surf, (25, 20))

        env_surf = font_med.render(
            f"ENVIRONMENT: {self.env.name.upper()} (g={self.env.gravity:.2f} m/s²)",
            True,
            (160, 175, 195),
        )
        screen.blit(env_surf, (25, 52))

        # Mode Indicator
        mode_str = (
            "[ AUTOPILOT GNC ENGAGED ]"
            if self.telemetry.autopilot_enabled
            else "[ MANUAL PILOT CONTROL ]"
        )
        mode_color = (
            (0, 255, 150) if self.telemetry.autopilot_enabled else (255, 200, 30)
        )
        mode_surf = font_large.render(mode_str, True, mode_color)
        screen.blit(mode_surf, (SCREEN_WIDTH - mode_surf.get_width() - 25, 20))

        # Touchdown Banner
        if self.telemetry.is_touchdown:
            status_color = (
                (0, 255, 120)
                if self.telemetry.status == FlightStatus.LANDED
                else (255, 50, 50)
            )
            banner_surf = font_large.render(
                self.telemetry.status.value + "!", True, status_color
            )
            screen.blit(
                banner_surf, (SCREEN_WIDTH // 2 - banner_surf.get_width() // 2, 75)
            )
            detail_surf = font_small.render(
                self.telemetry.status_detail, True, (240, 240, 240)
            )
            screen.blit(
                detail_surf, (SCREEN_WIDTH // 2 - detail_surf.get_width() // 2, 105)
            )

        # Telemetry Block (Top Right)
        hud_box_x = SCREEN_WIDTH - 280
        hud_box_y = 55
        hud_w = 255
        hud_h = 175
        pygame.draw.rect(
            screen,
            (15, 22, 35, 200),
            (hud_box_x, hud_box_y, hud_w, hud_h),
            border_radius=6,
        )
        pygame.draw.rect(
            screen,
            (0, 150, 220),
            (hud_box_x, hud_box_y, hud_w, hud_h),
            width=1,
            border_radius=6,
        )

        vy_color = (0, 255, 120) if abs(self.telemetry.vy) <= 4.0 else (255, 70, 70)
        telems = [
            (f"ALTITUDE AGL:  {self.telemetry.y:6.1f} m", (255, 255, 255)),
            (f"VERT SPEED:    {self.telemetry.vy:+6.1f} m/s", vy_color),
            (f"HORIZ DRIFT:   {self.telemetry.vx:+6.1f} m/s", (255, 255, 255)),
            (f"PAD OFFSET X:  {self.telemetry.x:+6.1f} m", (0, 220, 255)),
            (f"PITCH ANGLE:   {self.telemetry.pitch_degrees:+6.1f}°", (255, 255, 255)),
            (f"THROTTLE:      {self.telemetry.throttle * 100:5.0f} %", (255, 200, 30)),
            (f"GIMBAL:        {self.telemetry.gimbal_deg:+5.1f} °", (180, 200, 220)),
            (f"SUICIDE BURN:  {burn_alt:6.1f} m", (255, 230, 80)),
        ]
        for idx, (label, col) in enumerate(telems):
            t_surf = font_small.render(label, True, col)
            screen.blit(t_surf, (hud_box_x + 12, hud_box_y + 10 + (idx * 19)))

        # Fuel Meter (Left edge)
        fuel_pct = max(
            0.0, min(100.0, (self.telemetry.fuel / self.vehicle.fuel_capacity) * 100.0)
        )
        fuel_color = (0, 255, 120) if fuel_pct > 20.0 else (255, 60, 60)
        pygame.draw.rect(screen, (30, 35, 45), (25, 100, 18, 180), border_radius=3)
        bar_h = int((fuel_pct / 100.0) * 176)
        pygame.draw.rect(
            screen, fuel_color, (27, 100 + (176 - bar_h), 14, bar_h), border_radius=2
        )
        screen.blit(
            font_small.render(f"FUEL {fuel_pct:.0f}%", True, (180, 195, 210)), (20, 285)
        )

        # Bottom Controls Guide
        guide = "[↑/↓] Throttle  [←/→] Gimbal/RCS  [A] Autopilot  [Space] Engine Cut  [R] Reset  [1] Starship  [2] Falcon 9  [3] Lunar Lander"
        guide_surf = font_small.render(guide, True, (120, 135, 155))
        screen.blit(
            guide_surf,
            (SCREEN_WIDTH // 2 - guide_surf.get_width() // 2, SCREEN_HEIGHT - 35),
        )
