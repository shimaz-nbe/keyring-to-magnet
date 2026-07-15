from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

def _app_root() -> Path:
    """See pipeline.py::_app_root -- same reasoning, duplicated here rather
    than imported so this module still works standalone (e.g. under test)
    without depending on pipeline.py's import graph.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


_REPO_ROOT = _app_root()
_WIN_DOWNLOAD_URL = "https://potrace.sourceforge.net/download/1.16/potrace-1.16.win64.zip"

# Windows binaries need the .exe suffix to be runnable by name; macOS/Linux
# vendored binaries conventionally have none. shutil.which("potrace") below
# already covers a PATH-installed potrace (e.g. `brew install potrace` on
# macOS puts one on PATH), so this only affects the *vendored* fallback path.
_VENDORED_NAME = "potrace.exe" if sys.platform == "win32" else "potrace"


def find_potrace_exe(override: Path | None = None) -> Path:
    if override is not None and Path(override).is_file():
        return Path(override)
    env = os.environ.get("POTRACE_EXE")
    if env and Path(env).is_file():
        return Path(env)
    candidate = _REPO_ROOT / "vendor" / "potrace" / _VENDORED_NAME
    if candidate.is_file():
        return candidate
    if getattr(sys, "frozen", False):
        # A PyInstaller onefile exe normally already carries potrace bundled
        # internally (the `candidate` check above, resolved against the
        # per-run temp extraction dir) -- but a build made without a
        # vendored binary present has no such copy. sys.executable, unlike
        # __file__/_MEIPASS, points at the real .exe the user launched, so
        # this lets a manually-dropped potrace.exe sitting next to it be
        # found without any PATH/env var setup, matching the "just put it
        # in the same folder" portable-app pattern users tend to expect.
        sibling = Path(sys.executable).resolve().parent / _VENDORED_NAME
        if sibling.is_file():
            return sibling
    found = shutil.which("potrace")
    if found:
        return Path(found)

    if sys.platform == "darwin":
        hint = f"On macOS, the easiest route is `brew install potrace`, or place a binary at {candidate}."
    elif sys.platform == "win32":
        hint = f"Place it at {candidate}, or download the official Windows build: {_WIN_DOWNLOAD_URL}"
    else:
        hint = f"Install it via your package manager, or place a binary at {candidate}."
    raise FileNotFoundError(
        f"potrace executable not found. Set the POTRACE_EXE environment variable, add it to PATH, "
        f"or vendor it yourself. {hint}"
    )


def trace_to_svg(
    pbm_path: Path,
    svg_path: Path,
    *,
    turdsize: int = 2,
    alphamax: float = 1.0,
    opttolerance: float = 0.2,
    potrace_exe: Path | None = None,
) -> Path:
    exe = find_potrace_exe(potrace_exe)
    cmd = [
        str(exe),
        "-b", "svg",
        "-t", str(turdsize),
        "-a", str(alphamax),
        "-O", str(opttolerance),
        "-o", str(svg_path),
        str(pbm_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"potrace failed (exit {result.returncode}): {result.stderr}")
    return svg_path
