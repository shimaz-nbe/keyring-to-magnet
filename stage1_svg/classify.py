from __future__ import annotations

import math

from shapely.geometry import Polygon


def circularity(poly: Polygon) -> float:
    """4*pi*area / perimeter^2. 1.0 for a perfect circle, lower for anything else."""
    perimeter = poly.exterior.length
    if perimeter == 0:
        return 0.0
    return 4 * math.pi * poly.area / (perimeter ** 2)


def classify(regions: list[Polygon], circularity_min: float = 0.90) -> tuple[Polygon, Polygon]:
    """Split exactly 2 detected regions into (reference_circle, keyring).

    The scan protocol (see README) always contains exactly one keyring and one
    ~10mm reference circle, so classification only needs to pick the more
    circular of the two -- no size heuristic is needed or used.
    """
    if len(regions) != 2:
        raise ValueError(
            f"expected exactly 2 connected regions in the scan (one 10mm reference "
            f"circle + one keyring), found {len(regions)}. Check the scan for "
            "missing/extra objects, dust specks, or disconnected fragments."
        )
    scored = sorted(regions, key=circularity, reverse=True)
    best, other = scored
    if circularity(best) < circularity_min:
        raise ValueError(
            f"could not confidently identify the reference circle (best circularity "
            f"score {circularity(best):.3f}, need >= {circularity_min:.2f}). "
            "Check that the scan includes a clear, unbroken 10mm black circle."
        )
    return best, other
