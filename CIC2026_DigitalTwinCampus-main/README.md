# Campus Digital Twin

A proof-of-concept digital twin of a university campus floor at Myllypuro, developed as part of the **Digital Twins in Construction** course in the Computing in Construction programme at Metropolia University of Applied Sciences.

The project integrates a BIM model (IFC), real-time indoor sensor data, semantic data mapping, simulation logic, and interactive 3D visualization into a working prototype.

---

## Project Overview

The main objective is to create a digital twin of a campus floor by combining an IFC-based BIM model with real sensor data from the **Empathic Building** platform.

**Specific objectives:**

- **Real-time data integration** — retrieve live and historical sensor data via the Empathic Building API
- **Semantic data mapping** — map raw sensor data to building spaces using a lightweight Haystack-inspired semantic layer
- **Simulation logic** — implement rule-based and time-step simulations (occupancy, indoor air quality indicators)
- **3D visualization** — visualize sensor states and simulation results directly on BIM geometry in Blender
- **Modular architecture** — maintain a clean, Python-based codebase that is extensible and maintainable

## Features

- Building Information Modeling (BIM) integration via IFC
- Real-time data streaming with the Empathic Building platform (Pusher publish–subscribe)
- Historical sensor data playback
- 3D visualization in Blender with sensor overlays

## Tools & Stack

| Layer | Technology |
|-------|-----------|
| Language | Python |
| BIM / IFC parsing | IfcOpenShell |
| 3D visualization | Blender + Bonsai |
| Sensor platform | Empathic Building |
| Real-time messaging | Pusher (via Empathic Building) |

## Scope

**In scope:**
- One campus floor
- Selected indoor sensors (temperature, CO₂, occupancy)
- Read-only data integration
- Visual and analytical simulations

**Out of scope:**
- Full campus or city-scale deployment
- Real-time building control or actuation
- Full Project Haystack server or compliance implementation

## Input Data

- IFC model of a campus floor (geometry, rooms, doors, zones, metadata)
- Empathic Building sensor data
- Blender + Bonsai (Python) for simulation logic and visualization

## System Architecture

```
Empathic Building API
        ↓
Python Data Ingestion Layer
        ↓
Semantic Mapping Layer  (Haystack-inspired)
        ↓
Simulation State        (Python objects)
        ↓
Blender                 (BIM + Visualization)
Tree.js + web-ifc       (Web-based visualization)
```

**Data ingestion modes:**
- **Live mode** — Blender directly invokes Python modules to fetch data
- **Offline mode** — cached JSON files are used for reliability and demos

## Semantic Data Layer

A lightweight semantic layer inspired by Project Haystack is implemented in `services/haystack_converter.py`. It transforms raw Empathic Building API responses into Hayson-format entities, one entity per sensor point. These are written to `data/haystack_latest.json` and read directly by Blender.

Each entity represents a **sensor point**, not a room. Sensors are linked to spaces via `spaceRef` (an IFC GlobalId) when available, or matched via `space_mapping.json` as a fallback.

```json
{
    "id":           "r:3150275",
    "dis":          "occupancy-3150275",
    "point":        "m:",
    "sensor":       "m:",
    "siteRef":      "r:Myllypuro_Campus",
    "eb_id":        "3150275",
    "eb_type":      "occupancy",
    "eb_vendor":    "haltian",
    "eb_vendor_id": "TSPR04E2O84102880",
    "unlocated":    "m:",
    "occupancy":    "m:",
    "kind":         "Bool",
    "curVal":       false,
    "cur":          "m:",
    "curStatus":    "ok"
}
```

The `unlocated` marker tag indicates this sensor has not yet been matched to an IFC space. Sensors with a resolved `spaceRef` carry a `spaceRef` field instead, which `campus_dt_visualizer.py` uses to colour the corresponding IfcSpace object in Blender.

## Simulation Logic

Simulation runs inside the Blender + Bonsai scripting workspace. A single **Run Script** on `campus_dt_visualizer.py` does everything:

1. Reads `haystack_latest.json` fresh from disk
2. Makes IfcSpace objects visible, hides numeric-only zones
3. Colors each space by the active sensor type
4. Flags anomaly rooms (> `ANOMALY_THRESHOLD` σ from mean) in the console
5. Computes per-wing averages (wings A, B, C, D) and draws a summary panel
6. Shows sensor coverage gap in the legend footer
7. Starts an auto-refresh timer (repaints every `REFRESH_INTERVAL` seconds)
8. Draws the color-scale legend in the viewport HUD

Additional scripts handle supporting interactions:

| Script | Purpose |
|--------|---------|
| `dt_click_inspect.py` | Left-click any space to open a sensor popup |
| `dt_stop_timer.py` | Stop the auto-refresh timer |
| `legend_remove.py` | Remove all HUD overlays |

**Sensor type options** (set `ACTIVE_SENSOR_TYPE` in the script):

| Value | Sensor | Color scale |
|-------|--------|-------------|
| `"temperature"` | °C | Blue → Teal → Green → Amber → Red |
| `"co2"` | ppm | Green → Lime → Amber → Orange → Red |
| `"humidity"` | %RH | Red → Amber → Green → Amber → Red |
| `"occupancy"` | True/False | Green (occupied) / Blue (vacant) |
| `"comfort"` | 0–100 score | Teal → Green → Amber → Orange → Red |
| `"iaq_alert"` | occ × CO₂ | Green / Lime / Amber / Red / Yellow |

### How each sensor layer is calculated

**Comfort score** combines temperature comfort and CO₂ comfort at equal weight (50/50), each normalised 0–1, then multiplied by 100. Temperature peaks at 21–23 °C and ramps down to 0 at 18 °C or 27 °C. CO₂ is perfect at ≤ 600 ppm and drops to 0 at ≥ 1400 ppm. A room at ideal temperature but poor air quality scores 50, correctly reflecting that it is only half comfortable.

**IAQ alert** has five distinct states rather than a simple on/off:

| Color | State | Condition |
|-------|-------|-----------|
| Green | Vacant | Room unoccupied |
| Lime | Occupied, good air | CO₂ < 800 ppm |
| Amber | Occupied, watch | CO₂ 800–1200 ppm |
| Red | Occupied, alert | CO₂ > 1200 ppm |
| Yellow | No occupancy data | CO₂ sensor present but no occupancy sensor |

The yellow state is particularly useful — it flags rooms where air quality is visible but occupancy cannot be confirmed.

### Anomaly detection

The script computes a z-score per sensor type across all rooms. Any room beyond `ANOMALY_THRESHOLD` (default 1.5 σ from the mean) is flagged in the Blender console and has its description stored in the `dt_anomaly` custom property. This flag also appears in the click-to-inspect popup. Cold storage rooms or server rooms naturally appear as outliers and will consistently flag.

### Wing summary panel

Rooms are grouped by their first letter (wings A, B, C, D). The script computes average temperature, CO₂, and occupancy rate per wing and draws a compact 4-column grid in the viewport HUD above the legend. Each cell is color-coded independently using the same scale as the main visualization.

### Sensor coverage

The legend footer shows how many named IFC rooms have at least one matched sensor (e.g. `Coverage: 68/199 rooms`). This updates automatically on every refresh cycle and is a quick indicator of how much of the floor is instrumented.

## Project Workflow

1. Prepare IFC space mapping (run `20260315_IfcOpenShell.ipynb`)
2. Retrieve sensor data from Empathic Building API
3. Map raw data to semantic entities
4. Update simulation state
5. Trigger visual and animated feedback in Blender

## Outcome

A functional digital twin prototype demonstrating how BIM, real sensor data, semantic modelling, and simulation can be combined into an interactive 3D environment. The result serves as a reference architecture for small-scale digital twin development in the built environment.
Demo of web-ifc viewer in the folder [`web-ifc`](web-ifc) with a clean IFC model that is not included in the repository

---

## Documentation

Detailed step-by-step instructions are in the [`docs/`](docs/) folder:

| File | Contents |
|------|----------|
| [`docs/SETUP_AND_RUNNING.md`](docs/SETUP_AND_RUNNING.md) | Full guide — IFC preparation, sensor data, Blender + Bonsai setup |

## OMNIS-X integrated application

The existing IFC viewer is embedded in the OMNIS-X Campus Digital Twin page.
The backend is implemented with Python and aiohttp, with a persistent SQLite
database for local use and an optional MySQL schema in `mysql_schema.sql`.

```bash
py -3 -m pip install -r requirements.txt
py -3 app.py
```

Open `http://127.0.0.1:8080/`.

Demo login:

- Username: `admin`
- Password: `admin123`

Four portal demo users:

- `admin` / `admin123` – Admin
- `lecturer` / `demo123` – Lecturer
- `student` / `demo123` – Student
- `staff` / `demo123` – Local Staff

The sign-in page also supports account registration. New accounts are assigned
the Student role; usernames must be 3–32 characters, and passwords must be
8–128 characters.

After signing in, users select their role portal before opening the dashboard.
Only the portal matching the authenticated account is enabled.

The Student, Lecturer and Local Staff portals open on the problem reporting
page, where users can submit and track reports. High and Critical reports go
to the Admin queue, where administrators can assign or resolve them. Low and
Medium reports are sent to Google Gemini for automatic AI-assisted resolution
and are excluded from the Admin queue. The report title, description, category,
and location are sent to Gemini; reporter identity is not. Assigned lecturers
and local staff can update their work status and resolve assigned reports.
The Admin portal opens on incoming reports and hides failure simulation and
recovery-planning pages so administrators can focus on complaint resolution.

To enable automatic resolutions, copy `.env.example` to `.env` and set
`GEMINI_API_KEY` to a Google AI Studio API key. Keep `.env` local and never
commit the key. If Gemini is not configured or unavailable, low/medium reports
are not saved and the reporter receives an error to retry later. AI guidance
is marked as not physically verified.

The application exposes dashboard, resource, dependency, problem, assignment,
simulation, recovery, analytics, notification and WebSocket APIs in `app.py`.

MySQL deployment: import `mysql_schema.sql`. The local application currently
uses SQLite because no MySQL service was available during implementation.

## Team

Duy-Hien Ha · Chau Nguyen · Mohsen Parsaei  
Metropolia University of Applied Sciences — Computing in Construction, 2026
