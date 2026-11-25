# Setup & Running Guide

This document explains how to run the Campus Digital Twin from scratch — starting with IFC space mapping preparation, through data collection, to live visualization in Blender.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project structure](#2-project-structure)
3. [Step 1 — Prepare IFC space mapping (Jupyter notebook)](#3-step-1--prepare-ifc-space-mapping-jupyter-notebook)
4. [Discord bridge](#4-discord-bridge)
5. [Step 2 — Run the data collector](#5-step-2--run-the-data-collector)
6. [Step 3 — Visualize in Blender + Bonsai](#6-step-3--visualize-in-blender--bonsai)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites
- Python 3.10 or newer
- Access to the Empathic Building platform (email + password)
- Blender 4.x with the Bonsai add-on (for visualization)

### Clone / download the project

```bash
git clone <repo-url>
cd campus-digital-twin
```
### Install Python dependencies

A `requirements.txt` is provided with all needed packages.

```bash
python -m pip install -r requirements.txt
```

This installs:
- `requests` — HTTP client for the Empathic Building API
- `python-dotenv` — loads credentials from the `.env` file
- `ifcopenshell` and `lark` are also needed for the space mapping notebook 
> `ifcopenshell` may require a specific Python version — check the [IfcOpenShell releases](https://github.com/IfcOpenShell/IfcOpenShell/releases) for a pre-built wheel matching your version.

### Configure credentials in `.env`

Copy the template and fill in your details:

```bash
cp .env.example .env   # or just create .env from scratch
```

Edit `.env`:

```env
API_BASE_URL=https://eu-api.empathicbuilding.com
EB_EMAIL=your@email.com
EB_PASSWORD=your_password_here
GEMINI_API_KEY=your_google_ai_studio_key
```
> These credentials are read by `services/auth.py`. The resulting token is cached automatically in `data/token.json` and refreshed when it expires — you only need to export the variables once per terminal session.

> **Important:** `.env` is listed in `.gitignore` and must never be committed to version control.

The OMNIS-X app uses `GEMINI_API_KEY` for automatic AI-assisted resolution of
Low and Medium reports. It sends the report title, description, category, and
location to Google Gemini (not the reporter's username). High and Critical
reports continue to the Admin queue. If the key is missing or Gemini is
unavailable, the report is not saved and can be retried after configuration.

### Blender + Bonsai

1. Download **Blender** from [blender.org](https://www.blender.org/).
2. Install the **Bonsai** add-on from [bonsaibim.org](https://bonsaibim.org/).
   - In Blender: *Edit → Preferences → Add-ons → Install* → select the Bonsai `.zip`
   - Enable the add-on and restart Blender.
3. Load the IFC model via Bonsai: *File → Load IFC* → select `ARK_MET_F1.ifc`.

### IFC file

Place `ARK_MET_F1.ifc` in the project root. This file is **not tracked in git** — you must obtain it separately.

> If your IFC file has a different name, update `IFC_FILE` at the top of each notebook cell.

---

## 2. Project Structure

```
your_project/
├── IFC.blend                     ← open this in Blender
├── ARK_MET_F1.ifc                ← IFC model (not in git)
├── 20260318_IfcOpenShell CLEAN.ipynb   ← run first to prepare space mapping
├── main.py                       ← data collector entry point
├── .env                          ← credentials (never commit)
├── .env.example                  ← template to copy from
├── requirements.txt              ← pip dependencies
│
├── data/                         ← auto-created at runtime
│   ├── token.json                  cached auth token (auto-managed)
│   ├── space_mapping.json          IFC space ↔ sensor mapping (from notebook)
│   ├── haystack_latest.json        Blender always reads this file
│   ├── raw_latest.json
│   └── haystack_model_loc7_*.json  timestamped history (optional)
│
├── services/
│   ├── auth.py                   login + automatic token refresh
│   ├── eb_api.py                 Empathic Building REST API client
│   ├── haystack_converter.py     raw sensors → Project Haystack (Hayson)
│   └── collector.py              polling loop — fetches and saves data
│
└── blender/
    ├── make_all_transparent.py     ghost all building geometry
    ├── campus_dt_visualizer.py     color IfcSpaces by sensor data
    ├── dt_click_inspect.py         left-click any space for a sensor popup
    ├── dt_stop_timer.py            stop the auto-refresh timer
    └── legend_remove.py            clear both HUD overlays
```

> **Important — file layout:** The `data/` folder and `IFC.blend` must be siblings in the same directory. Blender scripts use `//data/Haystack_latest.json` (`//` = folder of the open `.blend` file). If your layout differs, update `HAYSTACK_JSON_PATH` at the top of each Blender script.

---

## 3. Step 1 — Prepare IFC space mapping (Jupyter notebook)

**Run this before anything else.** The notebook extracts space metadata from the IFC file and writes `data/space_mapping.json`, which is used by `haystack_converter.py` to match sensors to rooms.

```bash
jupyter notebook 20260318_IfcOpenShell CLEAN.ipynb
```

Run the cells **in order**:

| Cell | Output file | Notes |
|------|-------------|-------|
| Install dependency | — | Run once per environment |
| Step 1 — Inspect a space | — | Verify the IFC loads and check available fields |
| Step 2 — Extract all spaces | `data/space_mapping.json` | Core output — check duplicate warnings |
| Step 3 — Extract walls | `data/walls_with_spaces.json` | Intermediate file |
| Step 4 — Enrich walls | `data/walls_with_space_mapping.json` | Used by Blender |
| Step 5 — Space relations | `data/space_related_elements.json` | Used by Blender |

**Watch for duplicate space number warnings in Step 2.** If duplicates appear, they will cause ambiguous sensor-to-room matches. Resolve them in your BIM tool before proceeding.

After the notebook completes, confirm that `data/space_mapping.json` exists and contains the expected number of spaces.

---

## 4. Discord bridge

Start the viewer and Discord relay:

```bash
py -3 discord_bridge.py
```

Open `http://127.0.0.1:8080/`. The relay exposes its status at
`http://127.0.0.1:8080/api/health`.

To connect Discord, copy `.env.example` to `.env` and set:

```env
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_CHANNEL_ID=the_channel_for_room_updates
DISCORD_GUILD_ID=your_server_id
```

Enable the bot's application commands scope and install it in the server.
Slash commands currently available are `/twin_status`, `/twin_fit`, and
`/twin_panel`. Clicking a room in the viewer publishes its readings back to
the configured Discord channel.

## 5. Step 2 — Run the data collector

```bash
# Continuous polling — fetches data every 5 minutes
python main.py

# Single fetch and exit — useful for testing or before opening Blender
python main.py --once
```

This writes `data/haystack_latest.json` on every fetch cycle. Blender always reads this file.

**If the network is unavailable**, the previous `haystack_latest.json` is kept unchanged — Blender will show the last saved dataset.

---

## 6. Step 3 — Visualize in Blender + Bonsai

All five scripts live in `blender/`. Run them in the order below from the Blender **Scripting** workspace.

| Script | Purpose | Run order |
|--------|---------|-----------|
| `make_all_transparent.py` | Ghost all building geometry so space volumes are visible | 1 |
| `campus_dt_visualizer.py` | Color IfcSpaces by sensor data, draw HUD, start auto-refresh | 2 |
| `dt_click_inspect.py` | Left-click any space for a sensor popup | 3 (optional) |
| `dt_stop_timer.py` | Stop the auto-refresh timer | as needed |
| `legend_remove.py` | Clear both HUD overlays (legend + wing panel) | as needed |

### 6.1 Ghost the building geometry — `make_all_transparent.py`

Makes walls, slabs, columns, windows, and doors semi-transparent so the colored IfcSpace volumes are visible through the structure. IfcSpace objects are skipped automatically.

1. Open the **Scripting** workspace in Blender.
2. Open `blender/make_all_transparent.py` and press **Run Script**.

To adjust opacity for a whole element category (e.g. all walls), edit the `DT_ghost_IfcWall` material in the **Material Properties** panel — no need to re-run.

### 6.2 Colorize spaces — `campus_dt_visualizer.py`

The main script. Before running, open it and set the two values at the top:

```python
ACTIVE_SENSOR_TYPE = "temperature"          # choose from the table below
HAYSTACK_JSON_PATH = "//data/Haystack_latest.json"
```

Press **Run Script**. The script will:
- Read `haystack_latest.json` fresh from disk
- Color each IfcSpace by the active sensor type
- Detect anomaly rooms (> 1.5 σ from mean) and print them to the console
- Compute per-wing averages (A, B, C, D) and draw a summary panel in the viewport
- Draw a color-scale legend with sensor coverage
- Start a background auto-refresh timer (default: every 600 s)

Then switch the 3D viewport to **Material Preview** — press `Z` → Material Preview.

**Sensor type options:**

| Value | Sensor | Color scale |
|-------|--------|-------------|
| `"temperature"` | °C | Blue → Teal → Green → Amber → Red |
| `"co2"` | ppm | Green → Lime → Amber → Orange → Red |
| `"humidity"` | %RH | Blue → Teal → Green → Amber → Red |
| `"occupancy"` | True/False | Green (occupied) / Blue (vacant) |
| `"comfort"` | 0–100 score | Teal → Green → Amber → Orange → Red |
| `"iaq_alert"` | occ × CO₂ | Green / Lime / Amber / Red / Yellow |

To switch sensor layer: change `ACTIVE_SENSOR_TYPE` and press **Run Script** again.

To disable auto-refresh: set `REFRESH_INTERVAL = 0` before running.

### 6.3 Click-to-inspect — `dt_click_inspect.py` (optional)

Run after `campus_dt_visualizer.py`. Left-clicking any colored IfcSpace opens a popup with all sensor readings for that room, including an anomaly warning (⚠) if applicable.

Press **Run Script**, then left-click any space in the 3D viewport. Press **ESC** to exit inspect mode.

> Re-running this script while inspect mode is already active restarts it cleanly.

### 6.4 Utility scripts

- **`dt_stop_timer.py`** — stops the auto-refresh timer. Colors and HUD overlays are preserved.
- **`legend_remove.py`** — removes both HUD draw handlers. Space materials are not affected. Re-run `campus_dt_visualizer.py` to restore them.

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `FileNotFoundError: ARK_MET_F1.ifc` | IFC not in project root | Copy the file to the project root, or update `IFC_FILE` in the notebook |
| `No spaces found in the file` | Wrong IFC or corrupt file | Open in Bonsai to confirm it contains `IfcSpace` elements |
| `space_mapping.json not found` | Notebook not run yet | Run all cells in `20260314_IfcOpenShell.ipynb` in order |
| Duplicate space number warnings in Step 2 | Shared room numbers across floors | Resolve in your BIM tool, or update `floor_guid`/`floor_name` in the notebook |
| `haystack_latest.json` not found | Collector not run yet | Run `python main.py --once` before opening Blender |
| Blender shows old sensor data | Auto-refresh stopped or collector not running | Run `python main.py` in a terminal, or press **Run Script** on `campus_dt_visualizer.py` to force a reload |
| Spaces not colored in Blender | Viewport not in Material Preview | Press `Z` in the 3D viewport and select Material Preview |
| Sensor not matched to a room | Sensor has no `space_id` in EB API | `haystack_converter.py` applies a 4-level fuzzy match; unmatched sensors get the `unlocated` tag — check the console output |
| Token error / 401 Unauthorized | Credentials not exported | Re-run `export EB_EMAIL=...` and `export EB_PASSWORD=...` in the terminal |
