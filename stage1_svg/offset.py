from __future__ import annotations

from shapely.geometry import Polygon


def make_base_polygon(keyring_poly_mm: Polygon, offset_mm: float = 1.5) -> Polygon:
    """Offset the keyring's outer shell outward by `offset_mm`, uniformly along
    the curve normal (a true geometric buffer, not a scale) so the base extends
    past the keyring by the same distance everywhere regardless of local
    curvature. Any interior holes in the keyring are filled first: the base is
    a solid mounting plate, and punching the keyring's hole all the way through
    the 3.5mm base would be a structural weak point (holes are instead only
    reflected in the shallow keyring recess cut in Stage 2).
    """
    shell_only = Polygon(keyring_poly_mm.exterior)
    base = shell_only.buffer(offset_mm, join_style="round", quad_segs=16)
    return base.simplify(tolerance=0.05, preserve_topology=True)
