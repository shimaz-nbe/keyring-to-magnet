from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Stage1Config:
    ref_diameter_mm: float = 10.0
    base_offset_mm: float = 1.5
    circularity_min_for_reference: float = 0.90
    # 2 (potrace's own default) is too low for real scans -- dust/scanner
    # specks of a few px^2 routinely survive and get misread as extra
    # disconnected regions. 8 comfortably clears real dust while staying far
    # below the smallest legitimate hole an actual keyring/text print
    # produces (seen as low as ~500px^2 in printed logo text, and thousands
    # of px^2 for a real keyring's metal-ring mounting hole).
    potrace_turdsize: int = 8
    potrace_alphamax: float = 1.0
    potrace_opttolerance: float = 0.2
    samples_per_curve: int = 24
    canvas_padding_mm: float = 5.0
    median_blur_ksize: int = 5
    # Scans are taken of the keyring's flat back face (front has raised
    # relief that distorts the traced outline), which mirrors the result
    # left-right relative to the front-facing character. On by default so
    # the output matches the front-facing orientation; disable only if the
    # scan was already taken front-facing.
    flip_horizontal: bool = True
    # Stage 2 geometry, duplicated here only so Stage 1 can pre-flight-validate
    # that the detected keyring is large enough for the dual-magnet layout.
    hex_apothem_mm: float = 5.0
    hex_offset_from_center_mm: float = 8.0
    potrace_exe: Path | None = None
