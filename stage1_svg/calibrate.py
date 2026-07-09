from __future__ import annotations

import math

from shapely.geometry import Polygon


def compute_scale(ref_circle_poly: Polygon, known_diameter_mm: float = 10.0) -> float:
    """mm-per-svg-unit factor, derived from the reference circle's area-equivalent
    diameter (more robust to jagged tracing than using the raw bounding box).
    """
    d_units = 2 * math.sqrt(ref_circle_poly.area / math.pi)
    if d_units <= 0:
        raise ValueError("reference circle polygon has non-positive area; cannot calibrate scale")
    return known_diameter_mm / d_units
