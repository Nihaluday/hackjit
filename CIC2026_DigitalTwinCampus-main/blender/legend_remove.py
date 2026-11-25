"""
Campus Digital Twin – Remove HUD Overlays
==========================================
Removes the legend and wing summary panel draw handlers.
The colored spaces are not affected.
"""

import bpy

HANDLER_KEY      = "dt_legend_handler"
WING_HANDLER_KEY = "dt_wing_handler"

removed = []

for key, label in [(HANDLER_KEY, "legend"), (WING_HANDLER_KEY, "wing panel")]:
    handler = bpy.app.driver_namespace.pop(key, None)
    if handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(handler, "WINDOW")
        removed.append(label)

if removed:
    print(f"[DT] \u2713  Removed: {', '.join(removed)}")
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()
else:
    print("[DT]    No HUD overlays were registered.")
