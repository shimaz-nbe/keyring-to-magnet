"""Stage 2: 3 SVGs (ref_circle/keyring/base) -> printable STL, via Blender's
bundled Python. Run headless:

  blender --background --factory-startup --python stage2_model/build_model.py -- \\
      --base out/base.svg --keyring out/keyring.svg --calibration out/calibration.json \\
      --out out/model.stl [--out-obj out/model.obj] \\
      --base-thickness 3.5 --hex-apothem 5.0 --hex-height 5.0 --hex-bottom-z 1.0 \\
      --hex-offset 8.0 --keyring-cut-thickness 5.0 --keyring-cut-bottom-z 3.0

--factory-startup avoids the user's personal Blender preferences/add-ons
interfering with a reproducible headless run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402
from geometry_bpy import (  # noqa: E402
    boolean_diff,
    curve_to_mesh_object,
    export_stl,
    extrude_flat_mesh,
    import_svg_curve,
    keep_largest_spline,
    make_hex_prism,
    object_xy_center,
    scale_mesh_to_width,
    translate_mesh,
    validate_mesh,
)


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--keyring", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--out-obj", type=Path, default=None)
    parser.add_argument("--base-thickness", type=float, default=3.5)
    parser.add_argument("--hex-apothem", type=float, default=5.0)
    parser.add_argument("--hex-height", type=float, default=5.0)
    parser.add_argument("--hex-bottom-z", type=float, default=1.0)
    parser.add_argument("--hex-offset", type=float, default=8.0)
    parser.add_argument("--keyring-cut-thickness", type=float, default=5.0)
    parser.add_argument("--keyring-cut-bottom-z", type=float, default=3.0)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    calib = json.loads(args.calibration.read_text())

    keyring_width_mm = calib["keyring_bbox_mm"][2] - calib["keyring_bbox_mm"][0]
    base_width_mm = calib["base_bbox_mm"][2] - calib["base_bbox_mm"][0]

    bpy.ops.wm.read_factory_settings(use_empty=True)

    base_curve = import_svg_curve(args.base)
    base_mesh = curve_to_mesh_object(base_curve)
    scale_mesh_to_width(base_mesh, base_width_mm)
    extrude_flat_mesh(base_mesh, args.base_thickness)

    keyring_curve = import_svg_curve(args.keyring)
    keep_largest_spline(keyring_curve)
    keyring_mesh = curve_to_mesh_object(keyring_curve)
    scale_mesh_to_width(keyring_mesh, keyring_width_mm)
    center_xy = object_xy_center(keyring_mesh)
    print(f"placement center (blender space, mm): {center_xy}")

    left_center = (center_xy[0] - args.hex_offset, center_xy[1])
    right_center = (center_xy[0] + args.hex_offset, center_xy[1])
    hex_left = make_hex_prism("hex_left", left_center, args.hex_apothem, args.hex_height, args.hex_bottom_z)
    hex_right = make_hex_prism("hex_right", right_center, args.hex_apothem, args.hex_height, args.hex_bottom_z)

    boolean_diff(base_mesh, hex_left)
    boolean_diff(base_mesh, hex_right)

    extrude_flat_mesh(keyring_mesh, args.keyring_cut_thickness)
    translate_mesh(keyring_mesh, 0.0, 0.0, args.keyring_cut_bottom_z)
    boolean_diff(base_mesh, keyring_mesh)

    warnings = validate_mesh(base_mesh)
    for w in warnings:
        print(f"WARNING: {w}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    export_stl(base_mesh, args.out)
    print(f"wrote {args.out}")

    if args.out_obj:
        bpy.ops.object.select_all(action="DESELECT")
        base_mesh.select_set(True)
        bpy.context.view_layer.objects.active = base_mesh
        bpy.ops.wm.obj_export(filepath=str(args.out_obj), export_selected_objects=True, global_scale=1.0)
        print(f"wrote {args.out_obj}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
