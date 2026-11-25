"""
Campus Digital Twin – Stop Auto-Refresh Timer
=============================================
Run this to stop the background timer started by campus_dt_visualizer.py.
The colored spaces and legend are not affected.
"""

import bpy

TIMER_KEY        = "dt_refresh_timer"
HANDLER_KEY      = "dt_legend_handler"
WING_HANDLER_KEY = "dt_wing_handler"

# Stop timer
if bpy.app.driver_namespace.get(TIMER_KEY):
    bpy.app.driver_namespace[TIMER_KEY] = False   # signals modal to exit
    print("[DT] \u2713  Auto-refresh timer stopped.")
else:
    print("[DT]    No active timer found.")
