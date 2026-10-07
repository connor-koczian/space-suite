# 🚀 SpaceSuite — Astronautics & Rocketry Toolkit

A modular Python suite of spaceflight tools built from scratch for Ubuntu Linux.

## Modules

- **Module 1**: Live ISS Telemetry & Overhead Pass Alert (`iss-tracker`)
- **Module 2**: SpaceX & Rocket Launch Mission Control CLI (`space-suite launch`) *(Next)*
- **Module 3**: Starship / Lunar Lander "Suicide Burn" 2D Physics Simulator (`space-suite lander`) *(Roadmap)*

---

## Module 1: Live ISS Tracker & Overhead Pass Alert

### Key Features
1. **Live Orbital Telemetry**: Real-time downlink from the NORAD #25544 transponder via `api.wheretheiss.at` (Latitude, Longitude, Altitude, Orbital Velocity in km/h & km/s, Mach number, Solar Illumination / Earth Eclipse).
2. **3D Spherical & Orbital Geometry**:
   - **Haversine Distance**: Surface great-circle ground distance to observer.
   - **Slant Range**: Direct line-of-sight Euclidean distance taking altitude into account.
   - **Horizon Elevation Angle**: Geometric angle above local horizon ($\ge 0^\circ$ means line of sight).
   - **Compass Azimuth & Heading**: Forward bearing (e.g. $142^\circ$ SE).
3. **Ubuntu Desktop Notifications**: Native integration via `notify-send` when the ISS passes within visible range overhead, with intelligent pass debouncing and cooldown.
4. **Rich Terminal Dashboard**: Auto-refreshing, aerospace-styled terminal interface with historical telemetry trail and trend indicators.
5. **Pass Simulation Mode**: `--simulate-pass` flag to verify alerts and dashboard behavior immediately without waiting for an orbit pass.

---

## Quick Start (Ubuntu)

### Prerequisites
- Python $\ge$ 3.12 (managed via `uv`)
- `libnotify-bin` (`notify-send` is installed by default on Ubuntu)

### Installation
Dependencies are automatically managed with `uv`:
```bash
cd /home/connor/Projects/Connor/projects/space-suite
uv sync
```

### Usage Commands

#### 1. Test Desktop Notifications
Verify that Ubuntu desktop banners pop up:
```bash
uv run iss-tracker --test-notify
```

#### 2. Run Live ISS Tracker (Default: London / Greenwich)
```bash
uv run iss-tracker
```

#### 3. Run with Custom Ground Station Coordinates
Configure your exact latitude, longitude, and pass alert threshold:
```bash
uv run iss-tracker --lat 51.5074 --lon -0.1278 --name "Home Base" --threshold 1000
```

#### 4. Run Demonstration Pass Simulation
Simulates an overhead pass trajectory over 12 seconds so you can see the alert trigger and dashboard in action:
```bash
uv run iss-tracker --simulate-pass
```

#### 5. Top-Level Suite Launcher
```bash
uv run space-suite iss
```

---

## Testing & Quality Assurance
Run automated unit tests:
```bash
uv run pytest
```

Run code linter:
```bash
uv run ruff check .
```
