"""
Campus Digital Twin – Click-to-Inspect
=======================================
Blender + Bonsai scripting workspace.

Run this AFTER campus_dt_visualizer.py has colored the spaces.

Left-click any IfcSpace in the 3D viewport to open a popup showing
all sensor readings stored on that object.  Press ESC to stop.

How to use
----------
1. Run campus_dt_visualizer.py  (colors the spaces, writes dt_* properties)
2. Open this file in the Scripting workspace
3. Press Run Script
4. Click the 3D viewport to make it active
5. Left-click any colored space  →  popup appears
6. Press ESC inside the 3D viewport to stop

Re-running this script while inspect mode is already active will restart
it cleanly — no duplicates.

Why a separate file?
--------------------
The modal operator and popup dialog both require the active area to be the
3D viewport at the moment they are invoked.  Running them from within
campus_dt_visualizer.py (which runs in the Scripting workspace) means the
context is wrong and Blender silently drops the dialog.  This file uses
context override to force the correct area, which solves the problem.
"""

import bpy
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def find_view3d():
    """
    Return (area, region, region_data) for the first 3D viewport found
    in the current screen, or (None, None, None) if none exists.
    """
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        region     = next((r for r in area.regions if r.type == "WINDOW"), None)
        region_3d  = next((s.region_3d for s in area.spaces if s.type == "VIEW_3D"), None)
        if region and region_3d:
            return area, region, region_3d
    return None, None, None


def fmt_prop(val, unit="", decimals=1):
    """Format a dt_* custom property value for display."""
    if val is None or val == -1:
        return "no data"
    if isinstance(val, bool):
        return "yes" if val else "no"
    if isinstance(val, float):
        return f"{val:.{decimals}f}{unit}"
    return str(val)


# ─────────────────────────────────────────────────────────────────────
# OPERATOR 1 — popup dialog
# Invoked by the modal when a room is clicked.
# ─────────────────────────────────────────────────────────────────────

class DT_OT_InspectRoom(bpy.types.Operator):
    """Show sensor readings for the clicked IfcSpace in a popup dialog."""
    bl_idname  = "dt.inspect_room"
    bl_label   = "Room sensor data"
    bl_options = {"REGISTER"}

    room_number: bpy.props.StringProperty(default="")
    temp:        bpy.props.StringProperty(default="")
    co2:         bpy.props.StringProperty(default="")
    hum:         bpy.props.StringProperty(default="")
    occ:         bpy.props.StringProperty(default="")
    comfort:     bpy.props.StringProperty(default="")
    iaq:         bpy.props.StringProperty(default="")
    anomaly:     bpy.props.StringProperty(default="")

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Room:  {self.room_number}", icon="OBJECT_DATA")
        layout.separator()

        col = layout.column(align=True)
        col.scale_y = 1.1
        col.label(text=f"Temperature    :  {self.temp}")
        col.label(text=f"CO\u2082             :  {self.co2}")
        col.label(text=f"Humidity       :  {self.hum}")
        col.label(text=f"Occupied       :  {self.occ}")
        col.separator()
        col.label(text=f"Comfort score  :  {self.comfort}")
        col.label(text=f"IAQ status     :  {self.iaq}")

        if self.anomaly:
            layout.separator()
            row = layout.row()
            row.alert = True
            row.label(text=f"\u26a0  Anomaly:  {self.anomaly}", icon="ERROR")


# ─────────────────────────────────────────────────────────────────────
# OPERATOR 2 — modal click handler
# Runs as a persistent modal inside the 3D viewport.
# ─────────────────────────────────────────────────────────────────────

class DT_OT_ClickInspect(bpy.types.Operator):
    """Modal: left-click any IfcSpace to inspect its sensor data. ESC to exit."""
    bl_idname  = "dt.click_inspect"
    bl_label   = "DT Click-to-Inspect"
    bl_options = {"REGISTER"}

    def modal(self, context, event):
        # Stop on ESC
        if event.type == "ESC":
            bpy.app.driver_namespace.pop("dt_click_active", None)
            context.area.header_text_set(None)
            self.report({"INFO"}, "DT inspect mode stopped.")
            return {"CANCELLED"}

        # Ignore non-click events — pass through so navigation still works
        if event.type != "LEFTMOUSE" or event.value != "PRESS":
            return {"PASS_THROUGH"}

        # Ray-cast from mouse position into the 3D scene
        region = context.region
        rv3d   = context.region_data
        coord  = (event.mouse_region_x, event.mouse_region_y)

        origin    = region_2d_to_origin_3d(region, rv3d, coord)
        direction = region_2d_to_vector_3d(region, rv3d, coord)

        hit, _loc, _norm, _fi, obj, _mat = context.scene.ray_cast(
            context.view_layer.depsgraph, origin, direction
        )

        # Ignore non-IfcSpace objects. dt_anomaly is written to every visible
        # space by the visualizer, including those with no sensor match (grey).
        if not hit or obj is None or "dt_anomaly" not in obj:
            return {"PASS_THROUGH"}

        # Resolve room name: prefer the stored dt_room property; fall back to
        # the Blender object name so spaces with no sensor data still show up.
        room_name = obj.get("dt_room") or obj.name.split("/")[-1]

        # Collect properties — absent keys (no sensor data) display as "no data"
        kwargs = dict(
            room_number = str(room_name),
            temp        = fmt_prop(obj.get("dt_temp"),    " \u00b0C"),
            co2         = fmt_prop(obj.get("dt_co2"),     " ppm", 0),
            hum         = fmt_prop(obj.get("dt_hum"),     " %RH"),
            occ         = fmt_prop(obj.get("dt_occ")),
            comfort     = fmt_prop(obj.get("dt_comfort"), "/100", 0),
            iaq         = obj.get("dt_iaq")     or "no data",
            anomaly     = obj.get("dt_anomaly") or "",
        )

        print(f"[DT] Inspecting: {kwargs['room_number']}  "
              f"temp={kwargs['temp']}  co2={kwargs['co2']}  occ={kwargs['occ']}")

        # Invoke the popup dialog with a context override so it opens
        # in the 3D viewport even if the cursor is elsewhere on screen
        area, region_win, _ = find_view3d()
        if area:
            with bpy.context.temp_override(area=area, region=region_win):
                bpy.ops.dt.inspect_room("INVOKE_DEFAULT", **kwargs)
        else:
            bpy.ops.dt.inspect_room("INVOKE_DEFAULT", **kwargs)

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        if context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Click inside the 3D viewport first, then run again.")
            return {"CANCELLED"}

        context.area.header_text_set(
            "DT Inspect: left-click a colored space  |  ESC to stop"
        )
        bpy.app.driver_namespace["dt_click_active"] = True
        context.window_manager.modal_handler_add(self)
        self.report({"INFO"}, "DT inspect mode active — click any space.")
        return {"RUNNING_MODAL"}


# ─────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────

def main():
    # Register both operators (unregister first if already present)
    for cls in [DT_OT_InspectRoom, DT_OT_ClickInspect]:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
        bpy.utils.register_class(cls)

    # Find the 3D viewport and invoke the modal inside it
    area, region, _ = find_view3d()

    if area is None:
        print("[DT] \u2717  No 3D viewport found on this screen.")
        print("[DT]    Open a 3D viewport and run this script again.")
        return

    # Stop any existing instance cleanly before starting a new one
    bpy.app.driver_namespace.pop("dt_click_active", None)

    # Invoke the modal operator with a context override pointing at the viewport
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.dt.click_inspect("INVOKE_DEFAULT")

    print("[DT] \u2713  Click-to-inspect active.")
    print("[DT]    Left-click any colored space in the 3D viewport.")
    print("[DT]    ESC to stop.")


main()
