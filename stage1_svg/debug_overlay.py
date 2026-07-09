from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Polygon

# BGR colors
_COLOR_REF = (0, 0, 255)      # red
_COLOR_KEYRING = (0, 255, 255)  # yellow
_COLOR_BASE = (255, 255, 0)   # cyan


def _ring_to_px(coords, scale_mm_per_unit: float) -> np.ndarray:
    return np.array([[x / scale_mm_per_unit, y / scale_mm_per_unit] for x, y in coords], dtype=np.int32)


def _draw_polygon(canvas: np.ndarray, poly: Polygon, scale_mm_per_unit: float, color: tuple, thickness: int = 2) -> None:
    rings = [poly.exterior, *poly.interiors]
    for ring in rings:
        pts = _ring_to_px(list(ring.coords), scale_mm_per_unit)
        cv2.polylines(canvas, [pts], isClosed=True, color=color, thickness=thickness)


def write_debug_overlay(
    gray: np.ndarray,
    out_path: Path,
    scale_mm_per_unit: float,
    ref_circle_mm: Polygon,
    keyring_mm: Polygon,
    base_mm: Polygon,
) -> Path:
    canvas = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    _draw_polygon(canvas, base_mm, scale_mm_per_unit, _COLOR_BASE)
    _draw_polygon(canvas, keyring_mm, scale_mm_per_unit, _COLOR_KEYRING)
    _draw_polygon(canvas, ref_circle_mm, scale_mm_per_unit, _COLOR_REF)
    cv2.imwrite(str(out_path), canvas)
    return out_path
