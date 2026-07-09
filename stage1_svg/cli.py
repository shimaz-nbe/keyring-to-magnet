from __future__ import annotations

import argparse
import sys
from pathlib import Path

import shapely.affinity
from shapely.geometry import Point

from .calibrate import compute_scale
from .classify import circularity, classify
from .config import Stage1Config
from .debug_overlay import write_debug_overlay
from .offset import make_base_polygon
from .potrace_wrap import trace_to_svg
from .preprocess import binarize, flip_horizontal, load_grayscale, write_pbm
from .svg_writer import write_calibration_json, write_svgs
from .svgpath_parse import load_potrace_paths
from .validate import bbox_center, validate_hex_fit


def run_stage1(image_path: Path, outdir: Path, config: Stage1Config | None = None) -> dict:
    config = config or Stage1Config()
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    gray = load_grayscale(image_path)
    if config.flip_horizontal:
        gray = flip_horizontal(gray)
    binary = binarize(gray, blur_ksize=config.median_blur_ksize)

    pbm_path = outdir / "_scan.pbm"
    write_pbm(binary, pbm_path)

    raw_svg_path = outdir / "_potrace_raw.svg"
    trace_to_svg(
        pbm_path,
        raw_svg_path,
        turdsize=config.potrace_turdsize,
        alphamax=config.potrace_alphamax,
        opttolerance=config.potrace_opttolerance,
        potrace_exe=config.potrace_exe,
    )

    regions = load_potrace_paths(raw_svg_path, samples_per_curve=config.samples_per_curve)
    ref_poly_units, keyring_poly_units = classify(regions, config.circularity_min_for_reference)

    mm_per_unit = compute_scale(ref_poly_units, config.ref_diameter_mm)

    keyring_mm = shapely.affinity.scale(keyring_poly_units, xfact=mm_per_unit, yfact=mm_per_unit, origin=(0, 0))

    ref_centroid_units = ref_poly_units.centroid
    ref_center_mm = (ref_centroid_units.x * mm_per_unit, ref_centroid_units.y * mm_per_unit)
    ref_circle_mm = Point(ref_center_mm).buffer(config.ref_diameter_mm / 2.0, quad_segs=64)

    base_mm = make_base_polygon(keyring_mm, offset_mm=config.base_offset_mm)

    written = write_svgs(outdir, ref_circle_mm, keyring_mm, base_mm, padding_mm=config.canvas_padding_mm)

    keyring_center_mm = bbox_center(keyring_mm)
    keyring_bbox_mm = keyring_mm.bounds

    from shapely.ops import unary_union
    canvas_bounds = unary_union([ref_circle_mm, base_mm]).bounds
    canvas_width_mm = (canvas_bounds[2] - canvas_bounds[0]) + 2 * config.canvas_padding_mm
    canvas_height_mm = (canvas_bounds[3] - canvas_bounds[1]) + 2 * config.canvas_padding_mm

    calib_path = write_calibration_json(
        outdir,
        scale_mm_per_unit=mm_per_unit,
        ref_circle_center_mm=ref_center_mm,
        ref_circle_diameter_mm=config.ref_diameter_mm,
        keyring_bbox_center_mm=keyring_center_mm,
        keyring_bbox_mm=keyring_bbox_mm,
        base_bbox_mm=base_mm.bounds,
        canvas_width_mm=canvas_width_mm,
        canvas_height_mm=canvas_height_mm,
    )

    overlay_path = write_debug_overlay(
        gray, outdir / "debug_overlay.png", mm_per_unit, ref_circle_mm, keyring_mm, base_mm
    )

    hex_warnings = validate_hex_fit(
        base_mm, keyring_center_mm, config.hex_apothem_mm, config.hex_offset_from_center_mm
    )

    pbm_path.unlink(missing_ok=True)
    raw_svg_path.unlink(missing_ok=True)

    return {
        "svg_files": written,
        "calibration_json": calib_path,
        "debug_overlay": overlay_path,
        "scale_mm_per_unit": mm_per_unit,
        "ref_circularity": circularity(ref_poly_units),
        "keyring_bbox_mm": keyring_bbox_mm,
        "hex_fit_warnings": hex_warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 1: scanned keyring image -> SVG vectors + calibration")
    parser.add_argument("image", type=Path, help="path to the scanned image")
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--ref-diameter-mm", type=float, default=10.0)
    parser.add_argument("--base-offset-mm", type=float, default=1.5)
    parser.add_argument("--turdsize", type=int, default=None, help="default: Stage1Config.potrace_turdsize (8)")
    parser.add_argument("--alphamax", type=float, default=1.0)
    parser.add_argument("--opttolerance", type=float, default=0.2)
    parser.add_argument(
        "--no-flip",
        dest="flip_horizontal",
        action="store_false",
        default=True,
        help="scan is already front-facing; skip the default left-right mirror "
        "(by default, scans are assumed to be of the keyring's back face and are flipped)",
    )
    args = parser.parse_args(argv)

    config_defaults = Stage1Config()
    config = Stage1Config(
        ref_diameter_mm=args.ref_diameter_mm,
        base_offset_mm=args.base_offset_mm,
        potrace_turdsize=args.turdsize if args.turdsize is not None else config_defaults.potrace_turdsize,
        potrace_alphamax=args.alphamax,
        potrace_opttolerance=args.opttolerance,
        flip_horizontal=args.flip_horizontal,
    )

    try:
        result = run_stage1(args.image, args.outdir, config)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"Stage 1 failed: {e}", file=sys.stderr)
        return 1

    print(f"scale: {result['scale_mm_per_unit']:.5f} mm/unit")
    print(f"reference circle circularity: {result['ref_circularity']:.3f}")
    print(f"keyring bbox (mm): {result['keyring_bbox_mm']}")
    print(f"SVG files: {list(result['svg_files'].values())}")
    print(f"calibration.json: {result['calibration_json']}")
    print(f"debug overlay: {result['debug_overlay']}")
    if result["hex_fit_warnings"]:
        print("WARNINGS:")
        for w in result["hex_fit_warnings"]:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
