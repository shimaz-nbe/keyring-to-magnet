"""Orchestrator CLI. Two explicit subcommands with a human checkpoint between
them (see README):

  python pipeline.py stage1 SCAN_IMAGE --outdir out\\my_keyring
  # ... review out\\my_keyring\\debug_overlay.png ...
  python pipeline.py stage2 --outdir out\\my_keyring
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent


def _version_key(versioned_dir_name: str) -> tuple[int, int]:
    """Parses e.g. 'Blender 4.2' -> (4, 2) for numeric (not lexicographic)
    sorting, so 'Blender 10.0' correctly outranks 'Blender 9.0'."""
    m = re.search(r"(\d+)\.(\d+)", versioned_dir_name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _candidate_blender_paths() -> list[Path]:
    """Best-effort discovery of Blender installs in standard per-OS locations,
    newest version first. Blender's Windows installer versions its own
    install directory (e.g. "Blender 4.2", "Blender 5.1") without overwriting
    older installs, so a single hardcoded path breaks the moment a user is on
    a different version -- glob for any version instead. macOS installs are
    typically a single unversioned Blender.app, but some install flows keep
    versioned app bundles side by side, so the same glob-and-rank approach
    covers both. Always overridable via --blender-exe or BLENDER_EXE, which
    take priority over anything found here.
    """
    if sys.platform == "win32":
        bases = [Path(r"C:\Program Files\Blender Foundation"), Path(r"C:\Program Files (x86)\Blender Foundation")]
        found = [p for base in bases if base.is_dir() for p in base.glob("Blender */blender.exe")]
        return sorted(found, key=lambda p: _version_key(p.parent.name), reverse=True)
    if sys.platform == "darwin":
        found = list(Path("/Applications").glob("Blender*.app/Contents/MacOS/Blender"))
        return sorted(found, key=lambda p: _version_key(p.parent.parent.parent.name), reverse=True)
    return []


def find_blender_exe(override: str | None) -> Path:
    if override:
        p = Path(override)
        if p.is_file():
            return p
        raise FileNotFoundError(f"--blender-exe given but not found: {p}")
    env = os.environ.get("BLENDER_EXE")
    if env and Path(env).is_file():
        return Path(env)
    for candidate in _candidate_blender_paths():
        if candidate.is_file():
            return candidate
    found = shutil.which("blender")
    if found:
        return Path(found)

    if sys.platform == "win32":
        hint = r"install Blender to the default location (C:\Program Files\Blender Foundation\Blender <version>\blender.exe)"
    elif sys.platform == "darwin":
        hint = "install Blender to /Applications/Blender.app"
    else:
        hint = "install Blender and ensure it is on PATH"
    raise FileNotFoundError(
        f"blender executable not found. Set --blender-exe, set the BLENDER_EXE env var, or {hint}."
    )


def cmd_stage1(args: argparse.Namespace) -> int:
    from stage1_svg.cli import run_stage1
    from stage1_svg.config import Stage1Config

    config = Stage1Config(
        ref_diameter_mm=args.ref_diameter_mm,
        base_offset_mm=args.base_offset_mm,
        flip_horizontal=args.flip_horizontal,
    )
    outdir = Path(args.outdir)
    try:
        result = run_stage1(Path(args.image), outdir, config)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"Stage 1 failed: {e}", file=sys.stderr)
        return 1

    print(f"Stage 1 complete -> {outdir}")
    print(f"  scale: {result['scale_mm_per_unit']:.5f} mm/unit")
    print(f"  reference circle circularity: {result['ref_circularity']:.3f}")
    print(f"  keyring bbox (mm): {result['keyring_bbox_mm']}")
    print(f"  debug overlay: {result['debug_overlay']}")
    if result["hex_fit_warnings"]:
        print("  WARNINGS (Stage 2 will also check this):")
        for w in result["hex_fit_warnings"]:
            print(f"    - {w}")

    should_open = args.open_preview or (args.open_preview is None and sys.stdout.isatty())
    if should_open and sys.platform == "win32":
        try:
            os.startfile(result["debug_overlay"])  # type: ignore[attr-defined]
        except OSError:
            pass

    print("\nReview debug_overlay.png, then run:")
    print(f'  python pipeline.py stage2 --outdir "{outdir}"')
    return 0


def cmd_stage2(args: argparse.Namespace) -> int:
    from stage1_svg.validate import validate_hex_fit

    outdir = Path(args.outdir)
    calib_path = outdir / "calibration.json"
    if not calib_path.is_file():
        print(f"Stage 2 failed: {calib_path} not found -- run `stage1` first.", file=sys.stderr)
        return 1
    calib = json.loads(calib_path.read_text())

    # Re-validated here (not just trusted from Stage 1's own run) as a final
    # gate right before Blender is invoked, using the real base outline
    # re-parsed from base.svg (not just its bbox) -- catches e.g. a
    # hand-edited calibration.json or a base.svg swapped in after Stage 1.
    from stage1_svg.svgpath_parse import load_potrace_paths

    base_regions = load_potrace_paths(outdir / "base.svg")
    if len(base_regions) != 1:
        print(f"Stage 2 failed: expected exactly 1 shape in base.svg, found {len(base_regions)}", file=sys.stderr)
        return 1
    base_svg_poly = base_regions[0]
    warnings = validate_hex_fit(
        base_svg_poly,
        tuple(calib["keyring_bbox_center_mm"]),
        args.hex_apothem,
        args.hex_offset,
    )
    if warnings:
        print("Stage 2 aborted: magnet layout does not fit.", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
        return 1

    print(f"Stage 1 summary for {outdir}:")
    print(f"  scale: {calib['scale_mm_per_unit']:.5f} mm/unit")
    print(f"  reference circle diameter: {calib['ref_circle_diameter_mm']}mm")
    print(f"  keyring bbox (mm): {calib['keyring_bbox_mm']}")
    print(
        f"  magnet hex layout: apothem={args.hex_apothem}mm, "
        f"center-to-center={2*args.hex_offset}mm, base thickness={args.base_thickness}mm"
    )

    if not args.approve:
        if not sys.stdin.isatty():
            print(
                "Not an interactive session and --approve not given; aborting before Blender.",
                file=sys.stderr,
            )
            return 1
        reply = input(
            "Stage 1 output reviewed (see debug_overlay.png)? Proceed to Stage 2 (Blender 3D generation)? [y/N]: "
        )
        if reply.strip().lower() != "y":
            print("Aborted before Stage 2.")
            return 1

    blender_exe = find_blender_exe(args.blender_exe)
    build_script = _REPO_ROOT / "stage2_model" / "build_model.py"
    out_stl = outdir / "model.stl"
    cmd = [
        str(blender_exe),
        "--background",
        "--factory-startup",
        "--python", str(build_script),
        "--",
        "--base", str(outdir / "base.svg"),
        "--keyring", str(outdir / "keyring.svg"),
        "--calibration", str(calib_path),
        "--out", str(out_stl),
        "--base-thickness", str(args.base_thickness),
        "--hex-apothem", str(args.hex_apothem),
        "--hex-height", str(args.hex_height),
        "--hex-bottom-z", str(args.hex_bottom_z),
        "--hex-offset", str(args.hex_offset),
        "--keyring-cut-thickness", str(args.keyring_cut_thickness),
        "--keyring-cut-bottom-z", str(args.keyring_cut_bottom_z),
    ]
    if args.out_obj:
        cmd += ["--out-obj", str(outdir / "model.obj")]

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        print(f"Stage 2 failed: Blender exited with code {result.returncode}", file=sys.stderr)
        return 1

    print(f"Stage 2 complete -> {out_stl}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("stage1", help="scan image -> SVG vectors + calibration + preview")
    p1.add_argument("image", type=Path)
    p1.add_argument("--outdir", required=True)
    p1.add_argument("--ref-diameter-mm", type=float, default=10.0)
    p1.add_argument("--base-offset-mm", type=float, default=1.5)
    p1.add_argument("--open-preview", dest="open_preview", action="store_true", default=None)
    p1.add_argument("--no-open-preview", dest="open_preview", action="store_false")
    p1.add_argument(
        "--no-flip",
        dest="flip_horizontal",
        action="store_false",
        default=True,
        help="scan is already front-facing; skip the default left-right mirror "
        "(by default, scans are assumed to be of the keyring's back face and are flipped)",
    )
    p1.set_defaults(func=cmd_stage1)

    p2 = sub.add_parser("stage2", help="SVG vectors -> STL via headless Blender (human-approval gate)")
    p2.add_argument("--outdir", required=True)
    p2.add_argument("--approve", action="store_true", help="skip the interactive y/N prompt")
    p2.add_argument("--blender-exe", default=None)
    p2.add_argument("--base-thickness", type=float, default=3.5)
    p2.add_argument("--hex-apothem", type=float, default=5.0)
    p2.add_argument("--hex-height", type=float, default=5.0)
    p2.add_argument("--hex-bottom-z", type=float, default=1.0)
    p2.add_argument("--hex-offset", type=float, default=8.0)
    p2.add_argument("--keyring-cut-thickness", type=float, default=5.0)
    p2.add_argument("--keyring-cut-bottom-z", type=float, default=3.0)
    p2.add_argument("--out-obj", action="store_true", help="also export model.obj")
    p2.set_defaults(func=cmd_stage2)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
