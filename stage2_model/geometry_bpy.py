"""Geometry helpers used by build_model.py. Runs inside Blender's bundled
Python interpreter (bpy/bmesh/mathutils only -- no pip packages available).
"""
from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def import_svg_curve(svg_path: Path) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.import_curve.svg(filepath=str(svg_path))
    after = set(bpy.data.objects)
    new_objs = [o for o in (after - before) if o.type == "CURVE"]
    if len(new_objs) != 1:
        raise RuntimeError(f"expected exactly 1 curve object imported from {svg_path}, got {len(new_objs)}")
    return new_objs[0]


def _polygon_area(points: list[tuple[float, float]]) -> float:
    """Shoelace-formula area of a closed 2D polygon given as a point list (not
    assumed pre-closed). Only used to rank spline sizes against each other, so
    sign is irrelevant -- callers get an already-abs()'d value.
    """
    if len(points) < 3:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def keep_largest_spline(curve_obj: bpy.types.Object) -> None:
    """Strip every spline but the largest-area one from a curve object, in
    place. Potrace/Stage 1 legitimately encodes an interior hole in a traced
    shape (e.g. keyring.svg) as a second M...Z subpath -- correct for Stage 1's
    own calibration/debug-overlay use of that SVG, and Blender's SVG importer
    turns each such subpath into its own spline, correctly nested for
    fill_mode="BOTH" to punch a real hole through the filled mesh. That is
    undesirable specifically for the keyring *groove-cutter* mesh: a hole in
    the cutter leaves an un-recessed island of full-height material in the
    base. Call this on a freshly-imported curve, before
    curve_to_mesh_object(), for any curve used as a boolean cutter where only
    the outer silhouette should be filled -- never on the base/ref_circle
    curves, whose SVGs are already single-subpath by construction (Stage 1's
    make_base_polygon already strips holes via Polygon(.exterior) the same
    way). No-op if the curve already has 0 or 1 splines.
    """
    splines = curve_obj.data.splines
    if len(splines) <= 1:
        return

    def spline_xy(spline: bpy.types.Spline) -> list[tuple[float, float]]:
        if spline.type == "BEZIER":
            return [(p.co.x, p.co.y) for p in spline.bezier_points]
        return [(p.co.x, p.co.y) for p in spline.points]

    ranked = sorted(splines, key=lambda s: _polygon_area(spline_xy(s)), reverse=True)
    for spline in ranked[1:]:
        splines.remove(spline)


def scale_mesh_to_width(obj: bpy.types.Object, expected_width_mm: float) -> None:
    """Rescale a flat mesh (already converted from a curve) so its X width
    matches `expected_width_mm`, around the world origin.

    Blender's SVG importer resolves the file's own declared width/height/viewBox
    into an initial size (normally meters, since our SVGs declare physical "mm"
    units). Rather than trust that conversion is exact, we measure the imported
    object's own width and rescale it to match the *known* real-world width of
    that specific shape (recorded in Stage 1's calibration.json) -- this stays
    correct even if a different Blender version's SVG importer handles units
    differently. Done via bmesh (not object.transform_apply) because Blender
    refuses to apply scale to a still-2D curve object; by the time this runs
    the object is already a plain mesh, so no such restriction applies.
    """
    current_width = obj.dimensions.x
    if current_width <= 0:
        raise RuntimeError(f"object {obj.name} has zero width; cannot compute scale")
    factor = expected_width_mm / current_width

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.scale(bm, vec=(factor, factor, factor), verts=bm.verts[:])
    bm.to_mesh(obj.data)
    bm.free()


def curve_to_mesh_object(curve_obj: bpy.types.Object) -> bpy.types.Object:
    """Convert a filled 2D curve into a flat mesh object (z=0), via the
    evaluated depsgraph rather than the flakier `object.convert` operator.
    """
    curve_obj.data.dimensions = "2D"
    curve_obj.data.fill_mode = "BOTH"
    curve_obj.data.extrude = 0.0
    curve_obj.data.bevel_depth = 0.0

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = curve_obj.evaluated_get(depsgraph)
    mesh_data = bpy.data.meshes.new_from_object(eval_obj)
    mesh_obj = bpy.data.objects.new(curve_obj.name + "_mesh", mesh_data)
    bpy.context.collection.objects.link(mesh_obj)
    bpy.data.objects.remove(curve_obj, do_unlink=True)
    return mesh_obj


def extrude_flat_mesh(obj: bpy.types.Object, thickness_mm: float) -> None:
    """Extrude a flat (z=0) mesh upward into a solid spanning z=0..thickness_mm,
    with correct outward normals, deterministically (no Solidify offset-sign
    ambiguity).
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    ret = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    verts = [e for e in ret["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, thickness_mm), verts=verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()


def translate_mesh(obj: bpy.types.Object, dx: float, dy: float, dz: float) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.translate(bm, vec=(dx, dy, dz), verts=bm.verts[:])
    bm.to_mesh(obj.data)
    bm.free()


def object_xy_center(obj: bpy.types.Object) -> tuple[float, float]:
    corners = [Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    return (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0


def make_hex_prism(
    name: str,
    center_xy: tuple[float, float],
    apothem_mm: float,
    height_mm: float,
    bottom_z_mm: float,
    flat_facing_deg: float = 0.0,
) -> bpy.types.Object:
    """Hexagonal prism circumscribed about a circle of radius `apothem_mm`
    (flat-to-flat distance = 2*apothem_mm), spanning
    z=bottom_z_mm..bottom_z_mm+height_mm. flat_facing_deg=0 puts a flat face
    along +X, so two prisms placed left/right along X present parallel facing
    flats rather than a vertex poking into the neighboring pocket.
    """
    r = apothem_mm / math.cos(math.radians(30))
    verts_2d = [
        (
            center_xy[0] + r * math.cos(math.radians(flat_facing_deg + 30 + 60 * i)),
            center_xy[1] + r * math.sin(math.radians(flat_facing_deg + 30 + 60 * i)),
        )
        for i in range(6)
    ]

    mesh_data = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh_data)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    bm_verts = [bm.verts.new((x, y, bottom_z_mm)) for x, y in verts_2d]
    bm.faces.new(bm_verts)
    bm.to_mesh(mesh_data)
    bm.free()

    extrude_flat_mesh(obj, height_mm)
    return obj


def boolean_diff(target_obj: bpy.types.Object, cutter_obj: bpy.types.Object, solver: str = "EXACT") -> None:
    """target_obj -= cutter_obj, baked into target_obj's mesh data. cutter_obj
    is deleted afterward. Uses the EXACT solver (not FAST): our cutters are
    deliberately taller than the base so they poke fully through it, which is
    exactly the overlapping/coplanar-geometry case the manual recommends EXACT
    for.
    """
    mod = target_obj.modifiers.new(name="cut", type="BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter_obj
    mod.solver = solver

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = target_obj.evaluated_get(depsgraph)
    new_mesh = bpy.data.meshes.new_from_object(eval_obj)

    target_obj.modifiers.remove(mod)
    old_mesh = target_obj.data
    target_obj.data = new_mesh
    bpy.data.meshes.remove(old_mesh)
    bpy.data.objects.remove(cutter_obj, do_unlink=True)


def validate_mesh(obj: bpy.types.Object) -> list[str]:
    warnings: list[str] = []
    me = obj.data
    had_issues = me.validate(verbose=False)
    if had_issues:
        warnings.append("mesh.validate() found and fixed invalid geometry")

    bm = bmesh.new()
    bm.from_mesh(me)
    non_manifold = [e for e in bm.edges if not e.is_manifold]
    if non_manifold:
        warnings.append(f"{len(non_manifold)} non-manifold edges found")
    bm.free()
    return warnings


def export_stl(obj: bpy.types.Object, out_path: Path) -> None:
    # Our mesh vertex coordinates are already numerically in mm (baked in by
    # import_and_scale_to_mm and by building the hex prisms directly at mm
    # coordinates), and STL has no unit metadata -- slicers universally assume
    # its numbers are mm. So global_scale=1.0 (no further scaling) is correct.
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(
        filepath=str(out_path),
        export_selected_objects=True,
        ascii_format=False,
        global_scale=1.0,
    )
