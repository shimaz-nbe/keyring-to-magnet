# -*- mode: python ; coding: utf-8 -*-
# Build with: pyinstaller keyring_to_magnet.spec  (run from the repo root)
#
# Produces a single onefile exe bundling pipeline.py + its Python
# dependencies (opencv, shapely, trimesh, ...) so end users don't need
# Python installed. Blender is deliberately NOT bundled (hundreds of MB,
# and users may already have a version) -- `pipeline.py check` guides
# installing it. potrace IS bundled (it's tiny, ~200KB) when a local copy
# is present at build time, since asking a non-technical end user to also
# manually place a potrace binary would defeat the point of shipping an exe.
#
# Size notes (2026-07-14 measurement via a throwaway --onedir build):
# - opencv-python-headless (not opencv-python) is required in requirements.txt
#   -- the GUI variant pulls in a ~30MB ffmpeg DLL for video I/O we never use
#   (this pipeline only ever reads/writes still PNGs), plus GUI backend code
#   we never call (no imshow/waitKey anywhere in this codebase).
# - `scipy` and `PIL` are excluded below even though they show up in the
#   dependency graph: scipy is pulled in by PyInstaller's community shapely
#   hook (not by anything this project imports -- verified nothing here
#   imports scipy, and it's not even in requirements.txt), and PIL is an
#   optional soft-dependency inside svgelements (only used to decode raster
#   <image> elements embedded in an SVG -- this project only ever
#   generates/parses pure-vector SVGs, so that code path never runs). Both
# were confirmed non-fatal to exclude by rebuilding and re-running the full
# Stage1+Stage2 pipeline afterward -- if a future dependency bump makes one
# of these load-bearing, the exe will fail fast with an ImportError rather
# than silently misbehave.
from pathlib import Path

_repo_root = Path(SPECPATH)

datas = [
    (str(_repo_root / "stage2_model" / "build_model.py"), "stage2_model"),
    (str(_repo_root / "stage2_model" / "geometry_bpy.py"), "stage2_model"),
]

_potrace_exe = _repo_root / "vendor" / "potrace" / "potrace.exe"
if _potrace_exe.is_file():
    datas.append((str(_potrace_exe), "vendor/potrace"))
    _potrace_license = _repo_root / "vendor" / "potrace" / "COPYING"
    if _potrace_license.is_file():
        datas.append((str(_potrace_license), "vendor/potrace"))

a = Analysis(
    [str(_repo_root / "pipeline.py")],
    pathex=[str(_repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pyinstaller", "scipy", "PIL"],
    noarchive=False,
)

# Belt-and-suspenders: drop any video-I/O backend DLL that might still slip
# in via an opencv binary hook, even though opencv-python-headless shouldn't
# ship one. No-op (matches nothing) if headless is in fact clean.
a.binaries = [b for b in a.binaries if "ffmpeg" not in b[0].lower()]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="keyring-to-magnet",
    console=True,
    onefile=True,
    clean=False,
)
