"""
Campus Digital Twin – Space Sensor Visualizer + Legend
=======================================================
Blender + Bonsai scripting workspace.

One Run Script does everything:
  1. Reads Haystack_latest.json fresh from disk
  2. Makes IfcSpace objects visible, hides numeric-only zones
  3. Colors each space by the active sensor type
  4. Flags anomaly rooms (> ANOMALY_THRESHOLD σ from mean) in console
  5. Computes wing averages (A, B, C, D) and draws a summary panel
  6. Shows sensor coverage gap in the legend footer
  7. Starts an auto-refresh timer (repaints every REFRESH_INTERVAL s)
  8. Draws the color-scale legend in the viewport HUD

To click-inspect spaces:          run dt_click_inspect.py
To stop the auto-refresh timer:   run dt_stop_timer.py
To remove all HUD overlays:       run legend_remove.py
To refresh manually at any time:  press Run Script again

Sensor options — set ACTIVE_SENSOR_TYPE below:
  "temperature"  Blue → Teal → Green → Amber → Red        (°C)
  "co2"          Green → Lime → Amber → Orange → Red       (ppm)
  "humidity"     Red → Amber → Green → Amber → Red         (%RH)
  "occupancy"    Green (occupied) / Blue (vacant)
  "comfort"      Teal → Green → Amber → Orange → Red       (0–100)
  "iaq_alert"    Green / Lime / Amber / Red / Yellow
"""

import bpy
import blf
import gpu
import json
import os
import time
import statistics
from collections import defaultdict
from gpu_extras.batch import batch_for_shader
import ifcopenshell
from bonsai.bim.ifc import IfcStore
import bonsai.tool as tool


# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION — the only section you need to edit
# ─────────────────────────────────────────────────────────────────────

# Which sensor layer to visualize.
# Options: "temperature" | "co2" | "humidity" | "occupancy"
#          "comfort" | "iaq_alert"
ACTIVE_SENSOR_TYPE = "humidity"

# Path to Haystack JSON.  "//" = same folder as the .blend file.
HAYSTACK_JSON_PATH = "//data/Haystack_latest.json"

# Space volume opacity  (0.0 = invisible, 1.0 = solid)
SPACE_ALPHA = 0.4

# Legend position — bottom-left corner of the 3D viewport (pixels)
LEGEND_X = 20
LEGEND_Y = 20

# Wing panel sits above the legend
WING_PANEL_X = 20
WING_PANEL_Y = 380

# Auto-refresh interval in seconds (0 = disabled)
REFRESH_INTERVAL = 600

# Rooms this many standard deviations from the mean are flagged
ANOMALY_THRESHOLD = 1.5


# ─────────────────────────────────────────────────────────────────────
# SENSOR COLOR BANDS
# ─────────────────────────────────────────────────────────────────────

SENSOR_BANDS = {

    "temperature": [
        (19.0, (0.22, 0.54, 0.83), "cold"),
        (21.0, (0.11, 0.62, 0.46), "cool"),
        (23.0, (0.25, 0.65, 0.18), "comfortable"),
        (26.0, (0.94, 0.62, 0.15), "warm"),
        (99.0, (0.89, 0.30, 0.29), "hot"),
    ],

    "co2": [
        ( 600, (0.25, 0.65, 0.18), "excellent"),
        ( 800, (0.65, 0.83, 0.20), "good"),
        (1000, (0.94, 0.62, 0.15), "moderate"),
        (1200, (0.89, 0.50, 0.10), "poor"),
        (9999, (0.89, 0.30, 0.29), "bad"),
    ],

    "humidity": [
        # Dry side  → blue spectrum (cold/dry feel)
        # Humid side → red spectrum (warm/damp feel)
        # Comfortable centre → green
        ( 30.0, (0.89, 0.30, 0.29), "very_dry"),    # blue   < 30 %RH
        ( 40.0, (0.94, 0.62, 0.15), "dry"),         # teal   30–40 %RH
        ( 60.0, (0.25, 0.65, 0.18), "comfortable"), # green  40–60 %RH  ✓
        ( 70.0, (0.11, 0.62, 0.46), "humid"),       # amber  60–70 %RH
        (100.0, (0.22, 0.54, 0.83), "very_humid"),  # red    > 70 %RH
    ],

    "occupancy": {
        "occupied": (0.20, 0.78, 0.35),
        "vacant":   (0.22, 0.54, 0.83),
    },

    # Score = 50% temp comfort + 50% CO2 comfort, both normalised 0-1.
    # Temp peaks at 21-23 C; CO2 peaks at <=600 ppm.
    "comfort": [
        ( 20, (0.89, 0.30, 0.29), "very_poor"),
        ( 40, (0.89, 0.50, 0.10), "poor"),
        ( 60, (0.94, 0.62, 0.15), "moderate"),
        ( 80, (0.25, 0.65, 0.18), "good"),
        (100, (0.11, 0.62, 0.46), "great"),
    ],

    # Current readings: 329-500 ppm (building quiet).
    # Alert bands activate when building fills during class hours.
    "iaq_alert": {
        "vacant_ok":      (0.20, 0.78, 0.35),
        "occupied_ok":    (0.25, 0.65, 0.18),
        "occupied_watch": (0.94, 0.62, 0.15),
        "occupied_alert": (0.89, 0.30, 0.29),
        "no_occ_data":    (0.60, 0.55, 0.20),
    },
}

NO_DATA_COLOR = (0.50, 0.50, 0.50)

SENSOR_CONFIG = {
    "temperature": ("temp", "Temperature"),
    "co2":         ("co2",  "CO\u2082"),
    "humidity":    ("hum",  "Humidity"),
    "occupancy":   ("occ",  "Occupancy"),
    "comfort":     (None,   "Comfort score"),
    "iaq_alert":   (None,   "IAQ alert"),
}

LEGEND_ENTRIES = {

    "temperature": [
        ((0.22, 0.54, 0.83, 1.0), "< 19 \u00b0C    too cold"),
        ((0.11, 0.62, 0.46, 1.0), "19\u201321 \u00b0C   cool"),
        ((0.25, 0.65, 0.18, 1.0), "21\u201323 \u00b0C   comfortable"),
        ((0.94, 0.62, 0.15, 1.0), "23\u201326 \u00b0C   warm"),
        ((0.89, 0.30, 0.29, 1.0), "> 26 \u00b0C    too hot"),
        ((0.50, 0.50, 0.50, 0.5), "no data"),
    ],

    "co2": [
        ((0.25, 0.65, 0.18, 1.0), "< 600 ppm    excellent"),
        ((0.65, 0.83, 0.20, 1.0), "600\u2013800 ppm   good"),
        ((0.94, 0.62, 0.15, 1.0), "800\u20131000 ppm  moderate"),
        ((0.89, 0.50, 0.10, 1.0), "1000\u20131200 ppm poor"),
        ((0.89, 0.30, 0.29, 1.0), "> 1200 ppm   unhealthy"),
        ((0.50, 0.50, 0.50, 0.5), "no data"),
    ],

    "humidity": [
        ((0.89, 0.30, 0.29, 1.0), "< 30 %RH    very dry"),
        ((0.94, 0.62, 0.15, 1.0), "30\u201340 %RH   dry"),
        ((0.25, 0.65, 0.18, 1.0), "40\u201360 %RH   comfortable"),
        ((0.11, 0.62, 0.46, 1.0), "60\u201370 %RH   humid"),
        ((0.22, 0.54, 0.83, 1.0), "> 70 %RH    very humid"),
        ((0.50, 0.50, 0.50, 0.5), "no data"),
    ],

    "occupancy": [
        ((0.20, 0.78, 0.35, 1.0), "occupied"),
        ((0.22, 0.54, 0.83, 1.0), "vacant"),
        ((0.50, 0.50, 0.50, 0.5), "no data"),
    ],

    "comfort": [
        ((0.11, 0.62, 0.46, 1.0), "81\u2013100   great"),
        ((0.25, 0.65, 0.18, 1.0), "61\u201380    good"),
        ((0.94, 0.62, 0.15, 1.0), "41\u201360    moderate"),
        ((0.89, 0.50, 0.10, 1.0), "21\u201340    poor"),
        ((0.89, 0.30, 0.29, 1.0), "0\u201320     very poor"),
        ((0.50, 0.50, 0.50, 0.5), "no data (needs temp+CO\u2082)"),
    ],

    "iaq_alert": [
        ((0.25, 0.65, 0.18, 1.0), "occupied, CO\u2082 < 800 ppm"),
        ((0.94, 0.62, 0.15, 1.0), "occupied, CO\u2082 800\u20131200"),
        ((0.89, 0.30, 0.29, 1.0), "occupied, CO\u2082 > 1200 ppm"),
        ((0.20, 0.78, 0.35, 1.0), "vacant (any CO\u2082)"),
        ((0.60, 0.55, 0.20, 1.0), "CO\u2082 only, no occ. sensor"),
        ((0.50, 0.50, 0.50, 0.5), "no data"),
    ],
}

# driver_namespace keys — survive script re-runs
HANDLER_KEY      = "dt_legend_handler"
WING_HANDLER_KEY = "dt_wing_handler"
TIMER_KEY        = "dt_refresh_timer"
SENSOR_STATE_KEY = "dt_sensor_state"


# ═════════════════════════════════════════════════════════════════════
# PART 1 — SENSOR DATA LOADING
# ═════════════════════════════════════════════════════════════════════

def normalize_humidity(value, vendor):
    """platform_of_trust sends fractions (0.368 = 36.8 %RH). Fix to %RH."""
    if vendor == "platform_of_trust" and value < 1.0:
        return round(value * 100, 2)
    return round(value, 2)


def load_sensor_map(haystack_path, ifc_model):
    """
    Read Haystack_latest.json, match spaceRef GUIDs to IFC room numbers,
    aggregate multiple sensors per room, and return the sensor map.

    Returns { "C1504": {"temp": 22.1, "co2": 810.0, "hum": 45.3, "occ": True}, ... }
    """
    resolved_path = bpy.path.abspath(haystack_path)
    if not os.path.exists(resolved_path):
        print(f"[DT] \u2717  Haystack file not found: {resolved_path}")
        return {}

    print(f"[DT] Reading: {resolved_path}")
    with open(resolved_path, "r", encoding="utf-8") as f:
        haystack_data = json.load(f)
    print(f"[DT] Haystack entities loaded: {len(haystack_data)}")

    guid_to_room = {s.GlobalId: s.Name for s in ifc_model.by_type("IfcSpace")}

    raw_t = defaultdict(list)
    raw_c = defaultdict(list)
    raw_h = defaultdict(list)
    raw_o = defaultdict(list)

    for entity in haystack_data:
        sr = entity.get("spaceRef", "")
        if not sr:
            continue
        room = guid_to_room.get(sr.replace("r:", ""))
        if not room:
            continue
        val    = entity.get("curVal")
        et     = entity.get("eb_type", "")
        vendor = entity.get("eb_vendor", "")
        if val is None:
            continue
        if   et == "temperature": raw_t[room].append(float(val))
        elif et == "co2":         raw_c[room].append(float(val))
        elif et == "humidity":    raw_h[room].append(normalize_humidity(float(val), vendor))
        elif et == "occupancy":   raw_o[room].append(bool(val))

    def avg(v): return round(sum(v) / len(v), 2) if v else None

    all_rooms = set(raw_t) | set(raw_c) | set(raw_h) | set(raw_o)
    sensor_map = {
        room: {
            "temp": avg(raw_t[room]),
            "co2":  avg(raw_c[room]),
            "hum":  avg(raw_h[room]),
            "occ":  any(raw_o[room]) if raw_o[room] else None,
        }
        for room in all_rooms
    }

    print(f"[DT] Rooms with temperature : {len(raw_t)}")
    print(f"[DT] Rooms with CO\u2082         : {len(raw_c)}")
    print(f"[DT] Rooms with humidity    : {len(raw_h)}")
    print(f"[DT] Rooms with occupancy   : {len(raw_o)}")
    return sensor_map


# ═════════════════════════════════════════════════════════════════════
# PART 2 — DERIVED CALCULATIONS
# ═════════════════════════════════════════════════════════════════════

def comfort_score(temp, co2):
    """0-100 comfort = 50% temp sub-score + 50% CO2 sub-score. None if missing."""
    if temp is None or co2 is None:
        return None
    if   temp < 18:  t = 0.0
    elif temp < 21:  t = (temp - 18) / 3.0
    elif temp <= 23: t = 1.0
    elif temp <= 27: t = (27 - temp) / 4.0
    else:            t = 0.0
    c = max(0.0, min(1.0, (1400 - co2) / 800.0)) if co2 > 600 else 1.0
    return round((t * 0.5 + c * 0.5) * 100)


def iaq_alert_key(occ, co2):
    """Return the iaq_alert band key for a room. None = no sensor data at all."""
    if occ is None and co2 is None: return None
    if occ is None:                 return "no_occ_data"
    if not occ:                     return "vacant_ok"
    if co2 is None or co2 < 800:   return "occupied_ok"
    if co2 < 1200:                  return "occupied_watch"
    return "occupied_alert"


def compute_wing_stats(sensor_map):
    """
    Average sensor values per wing (first letter of room number).
    Returns { "A": {"temp": 22.1, "co2": 411, "occ_pct": 67,
                    "n_temp": 10, "n_co2": 8}, ... }
    """
    buckets = defaultdict(lambda: defaultdict(list))
    for room, data in sensor_map.items():
        if not room or not room[0].isalpha():
            continue
        wing = room[0].upper()
        if data["temp"] is not None: buckets[wing]["temp"].append(data["temp"])
        if data["co2"]  is not None: buckets[wing]["co2"].append(data["co2"])
        if data["occ"]  is not None: buckets[wing]["occ"].append(data["occ"])

    def avg(v): return round(sum(v) / len(v), 1) if v else None
    return {
        wing: {
            "temp":    avg(vals["temp"]),
            "co2":     avg(vals["co2"]),
            "occ_pct": round(100 * sum(vals["occ"]) / len(vals["occ"])) if vals["occ"] else None,
            "n_temp":  len(vals["temp"]),
            "n_co2":   len(vals["co2"]),
        }
        for wing, vals in buckets.items()
    }


def detect_anomalies(sensor_map, threshold=ANOMALY_THRESHOLD):
    """
    Find rooms whose temp or CO2 reading is more than `threshold` standard
    deviations from the global mean.
    Returns { "B1704": ["temp=18.0C (z=-3.9)"], ... }
    """
    temps = [(r, v["temp"]) for r, v in sensor_map.items() if v["temp"] is not None]
    co2s  = [(r, v["co2"])  for r, v in sensor_map.items() if v["co2"]  is not None]
    anomalies = defaultdict(list)

    for series, unit, fmt in [(temps, "\u00b0C", ".1f"), (co2s, "ppm", ".0f")]:
        if len(series) < 3:
            continue
        values = [v for _, v in series]
        mean   = statistics.mean(values)
        stdev  = statistics.stdev(values)
        if stdev == 0:
            continue
        for room, val in series:
            z = (val - mean) / stdev
            if abs(z) > threshold:
                label = "temp" if unit == "\u00b0C" else "CO\u2082"
                anomalies[room].append(f"{label}={val:{fmt}}{unit} (z={z:+.1f})")

    return dict(anomalies)


def compute_coverage(sensor_map, ifc_model):
    """Return (sensored_count, total_named_count) for the legend footer.

    Counts only valid rooms — i.e. IfcSpace entries whose name is not purely
    numeric.  This mirrors the hide logic in apply_to_spaces so that the
    denominator reflects exactly the spaces that are visible in the viewport.
    """
    total = sum(
        1 for s in ifc_model.by_type("IfcSpace")
        if not (str(s.Name) if s.Name is not None else "").strip().isdigit()
    )
    return len(sensor_map), total


# ═════════════════════════════════════════════════════════════════════
# PART 3 — MATERIALS
# ═════════════════════════════════════════════════════════════════════

def get_or_create_material(name, rgb, alpha):
    """Return named material; create if absent, refresh color on re-runs."""
    if name in bpy.data.materials:
        mat = bpy.data.materials[name]
        mat.diffuse_color = (*rgb, alpha)
        return mat
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes     = False
    mat.diffuse_color = (*rgb, alpha)
    mat.blend_method  = "BLEND"
    return mat


def material_for_value(sensor_type, value):
    """Map sensor_type + value to a Blender material."""
    bands = SENSOR_BANDS.get(sensor_type)
    if bands is None:
        return None
    if sensor_type == "occupancy":
        key = "occupied" if value else "vacant"
        return get_or_create_material(f"DT_{sensor_type}_{key}", bands[key], SPACE_ALPHA)
    if sensor_type == "iaq_alert":
        rgb = bands.get(value)
        if rgb is None: return None
        return get_or_create_material(f"DT_iaq_{value}", rgb, SPACE_ALPHA)
    for upper, rgb, label in bands:
        if value <= upper:
            return get_or_create_material(f"DT_{sensor_type}_{label}", rgb, SPACE_ALPHA)
    _, rgb, label = bands[-1]
    return get_or_create_material(f"DT_{sensor_type}_{label}", rgb, SPACE_ALPHA)


# ═════════════════════════════════════════════════════════════════════
# PART 4 — APPLY TO IFCSPACE OBJECTS
# ═════════════════════════════════════════════════════════════════════

def apply_to_spaces(ifc_model, sensor_map, sensor_type, anomalies):
    """
    Visibility, materials, and custom properties for every IfcSpace.

    Custom properties written
    -------------------------
    dt_temp     avg temperature C       (-1 = no data)
    dt_co2      avg CO2 ppm             (-1 = no data)
    dt_hum      avg humidity %RH        (-1 = no data)
    dt_occ      occupancy bool          (-1 = no data)
    dt_comfort  comfort score 0-100     (-1 = no data)
    dt_iaq      IAQ alert key string    ("" = no data)
    dt_anomaly  anomaly description     ("" = normal)
    dt_room     IFC room number
    """
    sensor_key  = SENSOR_CONFIG[sensor_type][0]
    no_data_mat = get_or_create_material("DT_no_data", NO_DATA_COLOR, SPACE_ALPHA * 0.5)
    matched = unmatched = no_object = hidden = 0

    for space in ifc_model.by_type("IfcSpace"):
        room_number = str(space.Name) if space.Name is not None else ""
        obj = tool.Ifc.get_object(space)
        if obj is None:
            no_object += 1
            continue

        if room_number.strip().isdigit():
            obj.hide_viewport = obj.hide_render = obj.hide_select = True
            hidden += 1
            continue

        obj.hide_viewport = obj.hide_render = obj.hide_select = False

        data      = sensor_map.get(room_number)
        temp      = data["temp"] if data else None
        co2       = data["co2"]  if data else None
        occ       = data["occ"]  if data else None
        score     = comfort_score(temp, co2)
        alert_key = iaq_alert_key(occ, co2)

        if data:
            obj["dt_temp"]    = data["temp"] if data["temp"] is not None else -1
            obj["dt_co2"]     = data["co2"]  if data["co2"]  is not None else -1
            obj["dt_hum"]     = data["hum"]  if data["hum"]  is not None else -1
            obj["dt_occ"]     = data["occ"]  if data["occ"]  is not None else -1
            obj["dt_comfort"] = score        if score        is not None else -1
            obj["dt_iaq"]     = alert_key    if alert_key    is not None else ""
            obj["dt_room"]    = room_number
        obj["dt_anomaly"] = ", ".join(anomalies.get(room_number, [])) or ""

        if   sensor_type == "comfort":   sensor_value = score
        elif sensor_type == "iaq_alert": sensor_value = alert_key
        else:                            sensor_value = data.get(sensor_key) if data else None

        if sensor_value is not None:
            mat = material_for_value(sensor_type, sensor_value)
            matched += 1
        else:
            mat = no_data_mat
            unmatched += 1

        if len(obj.material_slots) == 0:
            obj.data.materials.append(mat)
        else:
            obj.material_slots[0].material = mat

    return matched, unmatched, no_object, hidden


# ═════════════════════════════════════════════════════════════════════
# PART 5 — VIEWPORT DRAWING
# ═════════════════════════════════════════════════════════════════════

SWATCH_W  = 22
SWATCH_H  = 18
ROW_GAP   = 4
FONT_SIZE = 13


def draw_rect(x, y, w, h, color):
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch  = batch_for_shader(shader, "TRIS", {"pos": [
        (x,   y  ), (x+w, y  ), (x+w, y+h),
        (x,   y  ), (x+w, y+h), (x,   y+h),
    ]})
    shader.bind()
    shader.uniform_float("color", color)
    gpu.state.blend_set("ALPHA")
    batch.draw(shader)
    gpu.state.blend_set("NONE")


def draw_text(text, x, y, size, color=(1.0, 1.0, 1.0, 1.0)):
    font_id = 0
    blf.color(font_id, *color)
    blf.size(font_id, size)
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, text)


def draw_legend_callback(sensor_type, entries, title, coverage_text):
    """
    Color-scale legend panel with a coverage gap line in the footer.
    Drawn bottom-up from (LEGEND_X, LEGEND_Y).
    """
    row_h   = SWATCH_H + ROW_GAP
    n_rows  = len(entries)
    padding = 10

    # Background: extra height for title + coverage line
    draw_rect(
        LEGEND_X - padding, LEGEND_Y - padding,
        244, n_rows * row_h + 52 + padding * 2,
        (0.08, 0.08, 0.08, 0.75),
    )
    # Title
    draw_text(title, LEGEND_X, LEGEND_Y + n_rows * row_h + 28,
              FONT_SIZE + 1, (1.0, 1.0, 1.0, 0.95))
    # Coverage gap footer
    draw_text(coverage_text, LEGEND_X, LEGEND_Y + n_rows * row_h + 10,
              FONT_SIZE - 1, (0.70, 0.70, 0.70, 0.85))

    for i, (color, label) in enumerate(entries):
        row_y = LEGEND_Y + i * row_h
        draw_rect(LEGEND_X, row_y, SWATCH_W, SWATCH_H, color)
        # Swatch border
        for bx, by, bw, bh in [
            (LEGEND_X,              row_y,              1,        SWATCH_H),
            (LEGEND_X,              row_y,              SWATCH_W, 1),
            (LEGEND_X + SWATCH_W-1, row_y,              1,        SWATCH_H),
            (LEGEND_X,              row_y + SWATCH_H-1, SWATCH_W, 1),
        ]:
            draw_rect(bx, by, bw, bh, (1, 1, 1, 0.15))
        draw_text(label, LEGEND_X + SWATCH_W + 8,
                  row_y + (SWATCH_H - FONT_SIZE) // 2 + 1,
                  FONT_SIZE, (0.90, 0.90, 0.90, 1.0))


def draw_wing_callback(wing_stats):
    """
    Compact wing-average panel: columns A B C D, rows Temp / CO2 / Occ%.
    Positioned at (WING_PANEL_X, WING_PANEL_Y).
    """
    if not wing_stats:
        return

    wings   = sorted(wing_stats.keys())
    padding = 10
    row_h   = 20
    col_w   = 52
    label_w = 52
    panel_w = label_w + len(wings) * col_w
    panel_h = row_h * 4 + 6    # title + 3 data rows

    x0, y0 = WING_PANEL_X, WING_PANEL_Y

    draw_rect(x0 - padding, y0 - padding,
              panel_w + padding * 2, panel_h + padding * 2,
              (0.08, 0.08, 0.08, 0.75))

    # Header row
    draw_text("Wing avg", x0, y0 + panel_h - 4, FONT_SIZE, (1.0, 1.0, 1.0, 0.9))
    for i, wing in enumerate(wings):
        draw_text(wing, x0 + label_w + i * col_w + col_w // 2 - 4,
                  y0 + panel_h - 4, FONT_SIZE, (1.0, 1.0, 1.0, 0.95))

    # Row labels
    draw_text("Temp \u00b0C",  x0, y0 + row_h * 2 + 4, FONT_SIZE - 1, (0.75, 0.75, 0.75, 1.0))
    draw_text("CO\u2082 ppm", x0, y0 + row_h * 1 + 4, FONT_SIZE - 1, (0.75, 0.75, 0.75, 1.0))
    draw_text("Occ %",   x0, y0 + row_h * 0 + 4, FONT_SIZE - 1, (0.75, 0.75, 0.75, 1.0))

    for i, wing in enumerate(wings):
        s  = wing_stats[wing]
        cx = x0 + label_w + i * col_w

        # Temperature
        t     = s["temp"]
        t_str = f"{t:.1f}" if t is not None else "\u2014"
        t_col = (0.89, 0.30, 0.29, 1.0) if (t or 0) > 24 else \
                (0.25, 0.65, 0.18, 1.0) if (t or 0) > 20 else \
                (0.22, 0.54, 0.83, 1.0)
        draw_text(t_str, cx, y0 + row_h * 2 + 4, FONT_SIZE - 1, t_col)

        # CO2
        c     = s["co2"]
        c_str = f"{int(c)}" if c is not None else "\u2014"
        c_col = (0.89, 0.30, 0.29, 1.0) if (c or 0) > 1000 else \
                (0.94, 0.62, 0.15, 1.0) if (c or 0) > 800  else \
                (0.25, 0.65, 0.18, 1.0)
        draw_text(c_str, cx, y0 + row_h * 1 + 4, FONT_SIZE - 1, c_col)

        # Occupancy %
        p     = s["occ_pct"]
        p_str = f"{p}%" if p is not None else "\u2014"
        p_col = (0.20, 0.78, 0.35, 1.0) if (p or 0) > 50 else (0.75, 0.75, 0.75, 1.0)
        draw_text(p_str, cx, y0 + row_h * 0 + 4, FONT_SIZE - 1, p_col)


# ═════════════════════════════════════════════════════════════════════
# PART 6 — OPERATORS
# ═════════════════════════════════════════════════════════════════════


class DT_OT_RefreshTimer(bpy.types.Operator):
    """Timer that reloads Haystack JSON and repaints spaces automatically."""
    bl_idname = "dt.refresh_timer"
    bl_label  = "DT Auto-Refresh"

    _timer = None

    def modal(self, context, event):
        if event.type == "TIMER":
            if not bpy.app.driver_namespace.get(TIMER_KEY):
                self.cancel(context)
                return {"CANCELLED"}

            print(f"[DT] Auto-refresh at {time.strftime('%H:%M:%S')}")
            ifc_model = IfcStore.get_file()
            if ifc_model:
                sensor_map = load_sensor_map(HAYSTACK_JSON_PATH, ifc_model)
                if sensor_map:
                    anomalies = detect_anomalies(sensor_map)
                    apply_to_spaces(ifc_model, sensor_map, ACTIVE_SENSOR_TYPE, anomalies)
                    bpy.app.driver_namespace[SENSOR_STATE_KEY] = sensor_map
                    for area in context.screen.areas:
                        if area.type == "VIEW_3D":
                            area.tag_redraw()

        return {"PASS_THROUGH"}

    def execute(self, context):
        wm = context.window_manager
        self._timer = wm.event_timer_add(REFRESH_INTERVAL, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        print("[DT] Auto-refresh timer stopped.")


# ─────────────────────────────────────────────────────────────────────
# OPERATOR REGISTRATION
# ─────────────────────────────────────────────────────────────────────

_OPERATORS = [DT_OT_RefreshTimer]


def register_operators():
    for cls in _OPERATORS:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
        bpy.utils.register_class(cls)


# ─────────────────────────────────────────────────────────────────────
# DRAW HANDLER REGISTRATION
# ─────────────────────────────────────────────────────────────────────

def register_legend(sensor_type, coverage_text):
    old = bpy.app.driver_namespace.pop(HANDLER_KEY, None)
    if old:
        bpy.types.SpaceView3D.draw_handler_remove(old, "WINDOW")
    entries = LEGEND_ENTRIES.get(sensor_type, [])
    title   = f"Campus DT \u2014 {SENSOR_CONFIG[sensor_type][1]}"

    def cb():
        draw_legend_callback(sensor_type, entries, title, coverage_text)

    bpy.app.driver_namespace[HANDLER_KEY] = \
        bpy.types.SpaceView3D.draw_handler_add(cb, (), "WINDOW", "POST_PIXEL")


def register_wing_panel(wing_stats):
    old = bpy.app.driver_namespace.pop(WING_HANDLER_KEY, None)
    if old:
        bpy.types.SpaceView3D.draw_handler_remove(old, "WINDOW")

    def cb():
        draw_wing_callback(wing_stats)

    bpy.app.driver_namespace[WING_HANDLER_KEY] = \
        bpy.types.SpaceView3D.draw_handler_add(cb, (), "WINDOW", "POST_PIXEL")


# ═════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 60)
    print(f"  Campus DT \u2014 Sensor Visualizer [{ACTIVE_SENSOR_TYPE}]")
    print("=" * 60)

    if ACTIVE_SENSOR_TYPE not in SENSOR_BANDS:
        print(f"[DT] \u2717  Unknown sensor type: '{ACTIVE_SENSOR_TYPE}'")
        print(f"[DT]    Valid options: {list(SENSOR_BANDS.keys())}")
        return

    ifc_model = IfcStore.get_file()
    if not ifc_model:
        print("[DT] \u2717  No IFC model loaded. Open your .ifc via Bonsai first.")
        return

    print(f"[DT] IfcSpace elements in model: {len(ifc_model.by_type('IfcSpace'))}")

    # 1. Load sensor data
    sensor_map = load_sensor_map(HAYSTACK_JSON_PATH, ifc_model)
    if not sensor_map:
        print("[DT] \u2717  No sensor data loaded. Aborting.")
        return
    bpy.app.driver_namespace[SENSOR_STATE_KEY] = sensor_map

    # 2. Anomaly detection
    anomalies = detect_anomalies(sensor_map)
    if anomalies:
        print(f"\n[DT] \u26a0  Anomalies (>{ANOMALY_THRESHOLD}\u03c3 from mean) — {len(anomalies)} rooms:")
        for room, reasons in sorted(anomalies.items()):
            print(f"       {room:<14} {', '.join(reasons)}")
    else:
        print("[DT] Anomaly check: none detected.")

    # 3. Wing summary
    wing_stats = compute_wing_stats(sensor_map)
    print(f"\n[DT] Wing averages:")
    for wing in sorted(wing_stats):
        s = wing_stats[wing]
        t = f"{s['temp']}\u00b0C"  if s["temp"]    is not None else "\u2014"
        c = f"{s['co2']}ppm"       if s["co2"]     is not None else "\u2014"
        o = f"{s['occ_pct']}%"     if s["occ_pct"] is not None else "\u2014"
        print(f"       Wing {wing}: temp={t:<8} co2={c:<10} occ={o}")

    # 4. Coverage
    n_sensored, n_total = compute_coverage(sensor_map, ifc_model)
    coverage_text = f"Coverage: {n_sensored}/{n_total} rooms"
    print(f"\n[DT] {coverage_text}  ({n_total - n_sensored} without sensors)")

    # 5. Colorize spaces
    matched, unmatched, no_object, hidden = apply_to_spaces(
        ifc_model, sensor_map, ACTIVE_SENSOR_TYPE, anomalies
    )

    # 6. Register operators
    register_operators()

    # 7. Draw handlers
    register_legend(ACTIVE_SENSOR_TYPE, coverage_text)
    register_wing_panel(wing_stats)

    # 8. Auto-refresh timer
    if REFRESH_INTERVAL > 0:
        bpy.app.driver_namespace[TIMER_KEY] = True
        bpy.ops.dt.refresh_timer("INVOKE_DEFAULT")
        print(f"[DT] Auto-refresh every {REFRESH_INTERVAL}s  "
              f"(run dt_stop_timer.py to stop)")
    else:
        print("[DT] Auto-refresh disabled  (set REFRESH_INTERVAL > 0 to enable)")

    # 10. Force redraw
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()

    # Summary
    print()
    print(f"[DT] \u2713  Done \u2014 visualizing: {ACTIVE_SENSOR_TYPE}")
    print(f"       Colored by {ACTIVE_SENSOR_TYPE:<12} : {matched} spaces")
    print(f"       No sensor match (gray)   : {unmatched} spaces")
    print(f"       Hidden (numeric zones)   : {hidden} spaces")
    print(f"       No Blender object found  : {no_object} spaces")
    print()
    print("  Custom properties per space:")
    print("    dt_temp / dt_co2 / dt_hum / dt_occ / dt_comfort / dt_iaq / dt_anomaly / dt_room")
    print()
    print("  HUD overlays: legend (bottom-left) + wing panel (above legend)")
    print("  dt_click_inspect.py  \u2192 click any space for sensor popup")
    print("  dt_stop_timer.py     \u2192 stop auto-refresh")
    print("  legend_remove.py     \u2192 clear HUD overlays")
    print("  Z \u2192 Material Preview to see colors")
    print("=" * 60 + "\n")


main()
