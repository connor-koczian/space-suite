# 🚀 SpaceSuite — Astronautics & Rocketry Toolkit

A modular Python suite of spaceflight tools built from scratch for Ubuntu Linux.

## Modules

- **Module 1**: Live ISS Telemetry & Overhead Pass Alert (`iss-tracker`)
- **Module 2**: SpaceX & Rocket Launch Mission Control CLI (`launch-control`)
- **Module 3**: Starship / Lunar Lander "Suicide Burn" 2D Physics Simulator (`space-suite lander`) *(Next)*

---

## Module 1: Live ISS Tracker & Overhead Pass Alert

### Key Features
1. **Interactive Mission Control Web Dashboard (`--web`)**:
   - High-resolution photographic Earth satellite imagery from space (Esri World Imagery + OpenStreetMap layer switcher).
   - Moving sub-satellite marker (`🛰️`), continuous ground track path, and $\sim 2,200\text{ km}$ visibility footprint.
   - Pulsing home ground station marker (`📡`) and direct geodesic line of sight.
   - Apollo / ISS Quindar audio chime synthesizer via Web Audio API with UI toggle.
2. **Keplerian Orbital Mechanics**:
   - Calculates instantaneous orbital period ($T = 2\pi\sqrt{a^3/\mu} \approx 92.9\text{ mins}$) and daily orbits ($\sim 15.5\text{ laps/day}$).
3. **Dual-Redundant Telemetry Engine**:
   - Primary downlink: NORAD #25544 transponder via `api.wheretheiss.at`.
   - Secondary fallback: Open-Notify (`api.open-notify.org/iss-now.json`).
   - Zero-drop connection resilience with HTTP keep-alive recovery.
4. **3D Spherical & Orbital Geometry**:
   - **Haversine Distance**: Surface great-circle ground distance to observer.
   - **Slant Range**: Direct line-of-sight Euclidean distance taking altitude into account.
   - **Horizon Elevation Angle**: Geometric angle above local horizon ($\ge 0^\circ$ means line of sight).
   - **Compass Azimuth & Heading**: Forward bearing (e.g. $142^\circ$ SE).
5. **Ubuntu Desktop Notifications**: Native integration via `notify-send` when the ISS passes within visible range overhead, with intelligent pass debouncing and cooldown.
6. **Rich Terminal Dashboard**: Auto-refreshing, aerospace-styled terminal interface with historical telemetry trail and trend indicators.
7. **Pass Simulation Mode**: `--simulate-pass` flag or web button to verify alerts and dashboard behavior immediately without waiting for an orbit pass.

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

#### 5. Interactive Web Mission Control Dashboard
```bash
uv run iss-tracker --web
```
Access at `http://127.0.0.1:8055`.

---

## Module 2: SpaceX & Rocket Launch Mission Control

Track upcoming orbital launches worldwide (SpaceX Falcon 9, Falcon Heavy, Starship, NASA SLS, Rocket Lab Electron, etc.) with real-time countdown clocks, launchpad satellite mapping, and mission manifests.

### Key Features
1. **Interactive Mission Control Web Dashboard (`--web`)**:
   - Giant high-contrast T-minus / T-plus digital countdown timer.
   - Comprehensive mission dossiers (provider, rocket family, mission objective, launchpad location, target orbit).
   - Real-time filter toggles (`All Launches`, `SpaceX`, `Starship`, `NASA`).
   - Integrated Esri photographic satellite Earth view pinpointed on the exact launch complex (Cape Canaveral SLC-40, Kennedy Space Center LC-39A, Starbase Boca Chica, Vandenberg, etc.).
2. **Terminal Aerospace Live Dashboard**:
   - Auto-ticking countdown with status codes (`GO for Launch`, `TBD`, `Success`, `Hold`).
   - Manifest queue table displaying upcoming global flights.
3. **Resilient Launch Downlink Engine**:
   - Backed by Launch Library 2 API (`ll.thespacedevs.com`).
   - In-memory 60s smart cache to respect rate limits while maintaining sub-second local countdown accuracy.

### Usage Commands

#### 1. Live Terminal Launch Control
```bash
uv run launch-control
```

#### 2. Filter for SpaceX or Starship
```bash
uv run launch-control --filter SpaceX
uv run launch-control --filter Starship
```

#### 3. Interactive Web Mission Control Dashboard
```bash
uv run launch-control --web
```
Access at `http://127.0.0.1:8056`.

---

## Top-Level Suite Launcher

Launch any module directly from the unified CLI:
```bash
uv run space-suite iss
uv run space-suite launch
uv run space-suite launch --web
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
