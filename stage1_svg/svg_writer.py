from __future__ import annotations

import json
from pathlib import Path

import svgwrite
from shapely.geometry import Polygon
from shapely.ops import unary_union


def _ring_path_d(coords: list[tuple[float, float]]) -> str:
    d = f"M {coords[0][0]:.4f},{coords[0][1]:.4f} "
    d += " ".join(f"L {x:.4f},{y:.4f}" for x, y in coords[1:])
    return d + " Z"


def _polygon_path_d(poly: Polygon) -> str:
    d = _ring_path_d(list(poly.exterior.coords))
    for interior in poly.interiors:
        d += " " + _ring_path_d(list(interior.coords))
    return d


def write_svgs(
    outdir: Path,
    ref_circle_mm: Polygon,
    keyring_mm: Polygon,
    base_mm: Polygon,
    padding_mm: float = 5.0,
) -> dict[str, Path]:
    """Write ref_circle.svg / keyring.svg / base.svg sharing one absolute mm
    coordinate frame (same width/height/viewBox for all three), so importing
    them separately into Blender preserves their relative XY alignment.
    """
    minx, miny, maxx, maxy = unary_union([ref_circle_mm, base_mm]).bounds
    minx -= padding_mm
    miny -= padding_mm
    maxx += padding_mm
    maxy += padding_mm
    width = maxx - minx
    height = maxy - miny

    shapes = {
        "ref_circle.svg": ref_circle_mm,
        "keyring.svg": keyring_mm,
        "base.svg": base_mm,
    }
    written: dict[str, Path] = {}
    for filename, poly in shapes.items():
        dwg = svgwrite.Drawing(size=(f"{width:.4f}mm", f"{height:.4f}mm"))
        dwg.viewbox(minx, miny, width, height)
        dwg.add(dwg.path(d=_polygon_path_d(poly), fill="black", fill_rule="evenodd", stroke="none"))
        path = outdir / filename
        dwg.saveas(str(path))
        written[filename] = path
    return written


def write_calibration_json(
    outdir: Path,
    *,
    scale_mm_per_unit: float,
    ref_circle_center_mm: tuple[float, float],
    ref_circle_diameter_mm: float,
    keyring_bbox_center_mm: tuple[float, float],
    keyring_bbox_mm: tuple[float, float, float, float],
    base_bbox_mm: tuple[float, float, float, float],
    canvas_width_mm: float,
    canvas_height_mm: float,
) -> Path:
    data = {
        "scale_mm_per_unit": scale_mm_per_unit,
        "ref_circle_center_mm": list(ref_circle_center_mm),
        "ref_circle_diameter_mm": ref_circle_diameter_mm,
        "keyring_bbox_center_mm": list(keyring_bbox_center_mm),
        "keyring_bbox_mm": list(keyring_bbox_mm),
        "base_bbox_mm": list(base_bbox_mm),
        "canvas_width_mm": canvas_width_mm,
        "canvas_height_mm": canvas_height_mm,
    }
    path = outdir / "calibration.json"
    path.write_text(json.dumps(data, indent=2), encoding="ascii")
    return path
