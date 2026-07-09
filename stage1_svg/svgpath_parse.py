from __future__ import annotations

from pathlib import Path

from shapely.geometry import LinearRing, Polygon
from svgelements import SVG
from svgelements import Path as SvgPath
from svgelements import Move


def _unit_correction(svg: SVG) -> tuple[float, float, float]:
    """SVG width/height attributes declared with a physical unit (e.g. "pt" as
    Potrace does, or "mm" as our own svg_writer does) get resolved by
    svgelements against a fixed CSS px ratio when mapping the viewBox to
    element coordinates, which shifts parsed coordinates both in scale and
    (whenever the viewBox has a non-zero origin, as our own multi-shape SVGs
    do) in offset. This returns (factor, offset_x, offset_y), self-derived
    from whatever svgelements actually did (not a hardcoded 96/72 constant),
    such that `parsed_coord * factor + offset == original viewBox-space coord`
    (which for Potrace's default output equals the input PBM's pixel
    coordinates, and for our own SVGs equals real-world mm).
    """
    vb = svg.viewbox
    if vb is None or not svg.width:
        return 1.0, 0.0, 0.0
    factor = vb.width / svg.width
    return factor, vb.x, vb.y


def _flatten_subpath(
    segments: list, samples_per_curve: int, factor: float, offset_x: float, offset_y: float
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for seg in segments:
        if isinstance(seg, Move):
            points.append((seg.end.x * factor + offset_x, seg.end.y * factor + offset_y))
            continue
        for i in range(1, samples_per_curve + 1):
            t = i / samples_per_curve
            pt = seg.point(t)
            points.append((pt.x * factor + offset_x, pt.y * factor + offset_y))
    return points


def _split_subpaths(path: SvgPath) -> list[list]:
    subpaths: list[list] = []
    current: list = []
    for seg in path:
        if isinstance(seg, Move):
            if current:
                subpaths.append(current)
            current = [seg]
        else:
            current.append(seg)
    if current:
        subpaths.append(current)
    return subpaths


def load_potrace_paths(svg_path: Path, samples_per_curve: int = 24) -> list[Polygon]:
    """Parse a Potrace-generated SVG into shapely Polygons (with holes), one per
    connected foreground region.

    Potrace's own grouping of subpaths into <path> elements is not trustworthy
    as a proxy for "one connected region": for simple shapes (e.g. a plain
    circle, or a keyring with a single hole) it does emit one <path> per region
    with holes as extra subpaths, but for more complex shapes -- notably a
    keyring with printed text/logo on it, where each letter's counter is its
    own nested hole -- it instead emits many sibling <path> elements, one per
    contour, even though they all belong to the same physical blob. Trusting
    that grouping previously caused real scans to be misread as dozens of
    disconnected "regions".

    So every subpath from every <path> element is first flattened into one
    pool of rings, and regions are reconstructed from scratch by geometric
    containment (largest-area ring wins as a new top-level shell; anything
    else is filed as a hole of whichever shell's exterior contains its
    centroid) -- independent of which <path> a given subpath happened to be
    nested under.
    """
    svg = SVG.parse(str(svg_path))
    factor, offset_x, offset_y = _unit_correction(svg)
    svg_paths = [e for e in svg.elements() if isinstance(e, SvgPath)]

    all_rings: list[LinearRing] = []
    for p in svg_paths:
        for subpath_segments in _split_subpaths(p):
            pts = _flatten_subpath(subpath_segments, samples_per_curve, factor, offset_x, offset_y)
            if len(pts) < 3:
                continue
            ring = LinearRing(pts)
            if ring.is_empty or ring.length == 0:
                continue
            all_rings.append(ring)

    ranked = sorted(all_rings, key=lambda r: abs(Polygon(r).area), reverse=True)

    shells: list[LinearRing] = []
    holes_by_shell: list[list[LinearRing]] = []
    for ring in ranked:
        centroid = Polygon(ring).centroid
        parent_idx = next(
            (i for i, shell in enumerate(shells) if Polygon(shell).contains(centroid)),
            None,
        )
        if parent_idx is None:
            shells.append(ring)
            holes_by_shell.append([])
        else:
            holes_by_shell[parent_idx].append(ring)

    return [Polygon(shell, holes=holes_by_shell[i]) for i, shell in enumerate(shells)]
