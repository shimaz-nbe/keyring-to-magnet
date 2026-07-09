from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
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
