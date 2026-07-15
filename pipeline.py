"""Orchestrator CLI (see README).

Two explicit subcommands with a human checkpoint between them, for scans that
need debug_overlay.png reviewed before committing to Blender:

  python pipeline.py stage1 SCAN_IMAGE --outdir out\\my_keyring
  # ... review out\\my_keyring\\debug_overlay.png ...
  python pipeline.py stage2 --outdir out\\my_keyring

Or, once a scan setup is trusted (e.g. after validating enough real samples),
skip the manual checkpoint and go straight to STL:

  python pipeline.py run SCAN_IMAGE --outdir out\\my_keyring
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


def _app_root() -> Path:
    """Directory to resolve bundled resources (stage2_model/build_model.py,
    a vendored potrace binary) against. When frozen by PyInstaller (onefile),
    __file__ no longer points at a real sibling-file layout on disk -- data
    files added via --add-data are extracted fresh on each run to a temp
    directory exposed as sys._MEIPASS, so that's the root to use instead.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


_REPO_ROOT = _app_root()
_BLENDER_DOWNLOAD_URL = "https://www.blender.org/download/"


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


def _offer_open(url: str) -> None:
    """Print a download link and, in an interactive session, offer to open it
    in the default browser -- used to guide (not silently perform) installing
    a missing external dependency. Never auto-opens without asking: a
    double-clicked exe popping open a browser unprompted would be surprising.
    """
    if sys.stdin.isatty():
        try:
            reply = input(f"  Open {url} in your browser now? [y/N]: ")
        except EOFError:
            # isatty() can lie in some launch contexts (certain process
            # supervisors/automation harnesses attach a tty-like stdin that
            # then yields no actual input) -- fall back to just printing the
            # link rather than crashing the whole run over a yes/no prompt.
            print(f"  Download: {url}")
            return
        if reply.strip().lower() == "y":
            import webbrowser

            webbrowser.open(url)
    else:
        print(f"  Download: {url}")


def cmd_check(args: argparse.Namespace) -> int:
    """Report whether Blender and potrace are found, guiding installation for
    whichever is missing. Meant to be run standalone (`... check`) or as the
    friendly first thing a double-clicked exe shows (see main()) -- most
    end users of a packaged exe won't have either tool and won't know to look
    for a traceback buried in a console window that closes on exit.
    """
    from stage1_svg.potrace_wrap import find_potrace_exe

    all_ok = True

    print("Checking potrace...")
    try:
        print(f"  found: {find_potrace_exe(None)}")
    except FileNotFoundError as e:
        all_ok = False
        print(f"  NOT FOUND: {e}")
        if sys.platform == "win32":
            from stage1_svg.potrace_wrap import _WIN_DOWNLOAD_URL

            _offer_open(_WIN_DOWNLOAD_URL)
        elif sys.platform == "darwin":
            print("  Install with: brew install potrace")

    print("\nChecking Blender...")
    try:
        print(f"  found: {find_blender_exe(None)}")
    except FileNotFoundError as e:
        all_ok = False
        print(f"  NOT FOUND: {e}")
        _offer_open(_BLENDER_DOWNLOAD_URL)

    print()
    if all_ok:
        print("Both tools found. Ready to use `stage1` / `stage2` / `run`.")
    else:
        print("Install whichever tool is missing above, then run `check` again.")
    return 0 if all_ok else 1


def cmd_stage1(args: argparse.Namespace, standalone: bool = True) -> int:
    from stage1_svg.cli import run_stage1
    from stage1_svg.config import Stage1Config

    config = Stage1Config(
        ref_diameter_mm=args.ref_diameter_mm,
        base_offset_mm=args.base_offset_mm,
        flip_horizontal=args.flip_horizontal,
        **({"potrace_turdsize": args.turdsize} if args.turdsize is not None else {}),
    )
    outdir = Path(args.outdir)
    try:
        result = run_stage1(Path(args.image), outdir, config)
    except FileNotFoundError as e:
        print(f"Stage 1 failed: {e}", file=sys.stderr)
        print("Run `python pipeline.py check` for install guidance.", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError) as e:
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

    # `run` continues straight into Stage 2 itself -- this hint only makes
    # sense for the standalone `stage1` subcommand.
    if standalone:
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

    try:
        blender_exe = find_blender_exe(args.blender_exe)
    except FileNotFoundError as e:
        print(f"Stage 2 failed: {e}", file=sys.stderr)
        print("Run `python pipeline.py check` for install guidance.", file=sys.stderr)
        return 1
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


def cmd_run(args: argparse.Namespace) -> int:
    """Stage 1 immediately followed by Stage 2, with no debug_overlay.png
    review checkpoint in between (args.approve/open_preview are hardcoded via
    the `run` subparser's set_defaults). Intended for scan setups already
    validated on enough real samples that per-scan visual review is no longer
    needed -- see CLAUDE.md item 2 in the roadmap for the real-world testing
    that preceded enabling this.
    """
    rc = cmd_stage1(args, standalone=False)
    if rc != 0:
        return rc
    print()
    return cmd_stage2(args)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("stage1", help="scan image -> SVG vectors + calibration + preview")
    p1.add_argument("image", type=Path)
    p1.add_argument("--outdir", required=True)
    p1.add_argument("--ref-diameter-mm", type=float, default=10.0)
    p1.add_argument("--base-offset-mm", type=float, default=1.5)
    p1.add_argument(
        "--turdsize",
        type=int,
        default=None,
        help="potrace despeckle threshold in px^2; default: Stage1Config.potrace_turdsize (50). "
        "Lower this if debug_overlay.png shows a legitimate small hole/cutout getting filled in.",
    )
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

    p3 = sub.add_parser(
        "run",
        help="scan image -> STL directly (Stage 1 + Stage 2, no debug_overlay.png review checkpoint)",
    )
    p3.add_argument("image", type=Path)
    p3.add_argument("--outdir", required=True)
    p3.add_argument("--ref-diameter-mm", type=float, default=10.0)
    p3.add_argument("--base-offset-mm", type=float, default=1.5)
    p3.add_argument(
        "--turdsize",
        type=int,
        default=None,
        help="potrace despeckle threshold in px^2; default: Stage1Config.potrace_turdsize (50). "
        "Lower this if debug_overlay.png shows a legitimate small hole/cutout getting filled in.",
    )
    p3.add_argument(
        "--no-flip",
        dest="flip_horizontal",
        action="store_false",
        default=True,
        help="scan is already front-facing; skip the default left-right mirror "
        "(by default, scans are assumed to be of the keyring's back face and are flipped)",
    )
    p3.add_argument("--blender-exe", default=None)
    p3.add_argument("--base-thickness", type=float, default=3.5)
    p3.add_argument("--hex-apothem", type=float, default=5.0)
    p3.add_argument("--hex-height", type=float, default=5.0)
    p3.add_argument("--hex-bottom-z", type=float, default=1.0)
    p3.add_argument("--hex-offset", type=float, default=8.0)
    p3.add_argument("--keyring-cut-thickness", type=float, default=5.0)
    p3.add_argument("--keyring-cut-bottom-z", type=float, default=3.0)
    p3.add_argument("--out-obj", action="store_true", help="also export model.obj")
    p3.set_defaults(func=cmd_run, open_preview=False, approve=True)

    p4 = sub.add_parser("check", help="check whether Blender and potrace are found, and guide installing them if not")
    p4.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


def _main_frozen_no_args() -> int:
    """Entry point for a packaged exe launched with no arguments (i.e.
    double-clicked from Explorer rather than run from a terminal). argparse's
    normal "the following arguments are required" error would flash in a
    console window that Explorer closes the instant the process exits,
    before anyone could read it -- so this path runs the dependency check
    directly, prints basic usage, and waits for a keypress instead of just
    exiting.
    """
    print("Keyring to Magnet\n")
    cmd_check(argparse.Namespace())
    print(
        "\nUsage (run from a terminal in this exe's folder):\n"
        "  keyring-to-magnet.exe run SCAN_IMAGE --outdir out\\my_keyring\n"
        "  keyring-to-magnet.exe stage1 SCAN_IMAGE --outdir out\\my_keyring\n"
        "  keyring-to-magnet.exe stage2 --outdir out\\my_keyring\n"
        "  keyring-to-magnet.exe check\n"
    )
    try:
        input("Press Enter to exit...")
    except EOFError:
        pass
    return 0


if __name__ == "__main__":
    if getattr(sys, "frozen", False) and len(sys.argv) == 1:
        raise SystemExit(_main_frozen_no_args())
    raise SystemExit(main())
