from __future__ import annotations

import math

from shapely.geometry import Polygon


def bbox_center(poly: Polygon) -> tuple[float, float]:
    minx, miny, maxx, maxy = poly.bounds
    return ((minx + maxx) / 2.0, (miny + maxy) / 2.0)


def make_hex_polygon(center: tuple[float, float], apothem_mm: float, flat_facing_deg: float = 0.0) -> Polygon:
    """Hexagon circumscribed about a circle of radius `apothem_mm` (flat-to-flat
    distance = 2*apothem_mm). With flat_facing_deg=0 a flat side faces along +X,
    matching Stage 2's hex orientation so two side-by-side hexes present parallel
    facing flats rather than a vertex.
    """
    r = apothem_mm / math.cos(math.radians(30))
    pts = [
        (
            center[0] + r * math.cos(math.radians(flat_facing_deg + 30 + 60 * i)),
            center[1] + r * math.sin(math.radians(flat_facing_deg + 30 + 60 * i)),
        )
        for i in range(6)
    ]
    return Polygon(pts)


def validate_hex_fit(
    base_poly_mm: Polygon,
    center_mm: tuple[float, float],
    hex_apothem_mm: float = 5.0,
    hex_offset_from_center_mm: float = 8.0,
) -> list[str]:
    """Pre-flight check: do both magnet hex pockets fit entirely within the base
    outline? Returns a list of warning strings (empty if everything fits). This
    version intentionally does not attempt any fallback/alternate layout for
    keyrings too small for the standard layout -- callers should abort cleanly.
    """
    warnings: list[str] = []
    for side, sign in (("left", -1.0), ("right", 1.0)):
        hex_center = (center_mm[0] + sign * hex_offset_from_center_mm, center_mm[1])
        hex_poly = make_hex_polygon(hex_center, hex_apothem_mm)
        if not base_poly_mm.contains(hex_poly):
            warnings.append(
                f"{side} magnet hex pocket (center=({hex_center[0]:.1f}, {hex_center[1]:.1f})mm) "
                f"does not fully fit within the base outline -- keyring is too small/narrow for "
                f"the standard {2 * hex_offset_from_center_mm:.1f}mm dual-magnet layout. "
                "An alternate (e.g. single-magnet) layout is not implemented yet."
            )
    return warnings
