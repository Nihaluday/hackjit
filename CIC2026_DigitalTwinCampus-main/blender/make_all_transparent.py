"""
Campus Digital Twin – Make All Meshes Transparent
===================================================
Blender + Bonsai scripting workspace.

Run this script before visualize_spaces_by_temperature.py to prepare
the scene. It sets every mesh object (walls, slabs, columns, doors,
windows, etc.) to a low-opacity transparent material so the colored
IfcSpace volumes are clearly visible through the building geometry.

What it does:
  - Iterates every object in the scene that has mesh geometry
  - Skips objects whose name starts with "IfcSpace" — those are
    managed by the temperature visualizer and should keep their
    color materials untouched
  - Creates one shared transparent material per IFC type category
    (walls get one, slabs get another, etc.) to keep the material
    list clean and make bulk opacity changes easy
  - Writes a summary to the Blender console

Opacity guide:
  WALL_ALPHA    0.08  — almost invisible, just enough to see structure
  SLAB_ALPHA    0.05  — floors/ceilings even lighter
  DEFAULT_ALPHA 0.10  — all other mesh types

Usage:
  1. Open Blender with the IFC model loaded via Bonsai
  2. Open this file in the Scripting workspace
  3. Press Run Script (Alt+P)
  4. Then run visualize_spaces_by_temperature.py to paint the spaces

To undo: press Ctrl+Z in Blender, or run reset_materials.py.
"""

import bpy
from bonsai.bim.ifc import IfcStore
import bonsai.tool as tool


# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────

# Opacity per IFC element category. 0.0 = invisible, 1.0 = solid.
# Tune these values to taste — lower = more see-through.
ALPHA_BY_CATEGORY = {
    "IfcWall":              0.08,
    "IfcWallStandardCase":  0.08,
    "IfcSlab":              0.05,
    "IfcColumn":            0.10,
    "IfcBeam":              0.10,
    "IfcDoor":              0.06,
    "IfcWindow":            0.04,
    "IfcRailing":           0.06,
    "IfcStair":             0.08,
    "IfcStairFlight":       0.08,
    "IfcCurtainWall":       0.04,
    "IfcPlate":             0.06,
    "IfcMember":            0.08,
    "IfcCovering":          0.05,
    "IfcFurnishingElement": 0.06,
    "IfcBuildingElementProxy": 0.06,
}

# Fallback opacity for any IFC type not listed above
DEFAULT_ALPHA = 0.08

# Color for all transparent geometry: off-white works well in both
# light and dark viewport themes. Change to (0.3, 0.3, 0.3) for darker.
TRANSPARENT_RGB = (0.85, 0.85, 0.85)

# If True, IfcSpace objects are completely skipped so the temperature
# visualizer's color materials are never overwritten.
SKIP_IFC_SPACES = True


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def get_ifc_type(obj, ifc_model):
    """
    Return the IFC class string for a Blender object, e.g. "IfcWall".
    Returns None if the object is not linked to an IFC entity.
    """
    if ifc_model is None:
        return None
    try:
        ifc_entity = tool.Ifc.get_entity(obj)
        if ifc_entity:
            return ifc_entity.is_a()
    except Exception:
        pass
    return None


def get_or_create_transparent_material(ifc_type, rgb, alpha):
    """
    Return a shared transparent material for the given IFC type.
    Using one material per type (rather than one per object) keeps
    the .blend material list short and lets you change the opacity
    of all walls at once just by editing the DT_ghost_IfcWall material.
    """
    mat_name = f"DT_ghost_{ifc_type}"

    if mat_name in bpy.data.materials:
        mat = bpy.data.materials[mat_name]
        # Refresh values in case the script is re-run with new settings
        mat.diffuse_color = (*rgb, alpha)
        return mat

    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes     = False
    mat.diffuse_color = (*rgb, alpha)
    mat.blend_method  = "BLEND"
    """ mat.shadow_method = "NONE" """
    return mat


def assign_material(obj, mat):
    """Assign mat as the first (and only) material slot on obj."""
    if len(obj.material_slots) == 0:
        obj.data.materials.append(mat)
    else:
        obj.material_slots[0].material = mat
        # Clear any extra slots so previous multi-material objects look clean
        while len(obj.material_slots) > 1:
            obj.active_material_index = 1
            bpy.ops.object.material_slot_remove({"object": obj})


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 56)
    print("  Campus DT – Make All Meshes Transparent")
    print("=" * 56)

    ifc_model = IfcStore.get_file()
    if not ifc_model:
        print("[DT] ✗  No IFC model loaded.")
        print("[DT]    Open your .ifc file via Bonsai first, then re-run.")
        return

    # Counters for the summary
    count_made_transparent = 0
    count_skipped_space    = 0
    count_skipped_no_mesh  = 0
    type_counts            = {}

    for obj in bpy.data.objects:

        # Skip anything that is not renderable geometry
        if obj.type != "MESH":
            count_skipped_no_mesh += 1
            continue

        # Identify the IFC type for this object
        ifc_type = get_ifc_type(obj, ifc_model) or "Unknown"

        # Skip IfcSpace — managed by the temperature visualizer
        if SKIP_IFC_SPACES and ifc_type == "IfcSpace":
            count_skipped_space += 1
            continue

        # Determine opacity for this element category
        alpha = ALPHA_BY_CATEGORY.get(ifc_type, DEFAULT_ALPHA)

        # Get or create the shared ghost material for this type
        mat = get_or_create_transparent_material(
            ifc_type, TRANSPARENT_RGB, alpha
        )

        # Apply to object
        assign_material(obj, mat)

        count_made_transparent += 1
        type_counts[ifc_type] = type_counts.get(ifc_type, 0) + 1

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n[DT] ✓  Done.")
    print(f"       Objects made transparent : {count_made_transparent}")
    print(f"       IfcSpace objects skipped : {count_skipped_space}")
    print(f"       Non-mesh objects skipped : {count_skipped_no_mesh}")
    print()
    print("  Transparent objects by IFC type:")
    for ifc_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        alpha = ALPHA_BY_CATEGORY.get(ifc_type, DEFAULT_ALPHA)
        print(f"    {ifc_type:<35} {count:>4} objects  (alpha {alpha})")
    print()
    print("  Materials created (one shared per type):")
    ghost_mats = [m for m in bpy.data.materials if m.name.startswith("DT_ghost_")]
    for mat in sorted(ghost_mats, key=lambda m: m.name):
        print(f"    {mat.name}")
    print()
    print("  Tip: edit a DT_ghost_* material's alpha in the Material")
    print("  Properties panel to adjust opacity for that entire category.")
    print("  → Switch viewport to Material Preview (Z → Material Preview)")
    print("=" * 56 + "\n")

    # Trigger viewport redraw
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


main()
