"""Generate a synthetic scan PNG for testing Stage 1/2 without a real scanner.

Draws a black circle of known real-world diameter (the "10mm reference circle")
and an irregular wobbly blob with an interior hole (a keyring surrogate) on a
white canvas, at a chosen DPI. The DPI is only used to *render* the image; the
pipeline under test must never be told the DPI and must recover scale purely
from the reference circle, exactly as it would with a real scan.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

CANVAS_WIDTH_MM = 140.0
CANVAS_HEIGHT_MM = 90.0
REF_CIRCLE_CENTER_MM = (25.0, 45.0)
REF_CIRCLE_DIAMETER_MM = 10.0
BLOB_CENTER_MM = (90.0, 45.0)
BLOB_RADIUS_X_MM = 25.0
BLOB_RADIUS_Y_MM = 18.0
BLOB_WOBBLE_AMPLITUDE = 0.18
HOLE_RADIUS_X_MM = 6.0
HOLE_RADIUS_Y_MM = 4.0
HOLE_WOBBLE_AMPLITUDE = 0.15


def wobbly_ring_points(
    center_mm: tuple[float, float],
    radius_x_mm: float,
    radius_y_mm: float,
    wobble_amplitude: float,
    rng: np.random.Generator,
    n_points: int = 96,
) -> list[tuple[float, float]]:
    angles = np.linspace(0.0, 2.0 * math.pi, n_points, endpoint=False)
    k1, k2 = rng.integers(2, 5), rng.integers(5, 9)
    phase1, phase2 = rng.uniform(0, 2 * math.pi, size=2)
    wobble = 1.0 + wobble_amplitude * (
        0.6 * np.sin(k1 * angles + phase1) + 0.4 * np.sin(k2 * angles + phase2)
    )
    xs = center_mm[0] + radius_x_mm * wobble * np.cos(angles)
    ys = center_mm[1] + radius_y_mm * wobble * np.sin(angles)
    return list(zip(xs.tolist(), ys.tolist()))


def mm_to_px(pt_mm: tuple[float, float], dpi: float) -> tuple[float, float]:
    return (pt_mm[0] / 25.4 * dpi, pt_mm[1] / 25.4 * dpi)


def render(dpi: float, seed: int, with_hole: bool, noise: bool) -> Image.Image:
    rng = np.random.default_rng(seed)
    width_px = round(CANVAS_WIDTH_MM / 25.4 * dpi)
    height_px = round(CANVAS_HEIGHT_MM / 25.4 * dpi)

    img = Image.new("L", (width_px, height_px), color=255)
    draw = ImageDraw.Draw(img)

    ref_radius_mm = REF_CIRCLE_DIAMETER_MM / 2.0
    cx_mm, cy_mm = REF_CIRCLE_CENTER_MM
    bbox = [
        mm_to_px((cx_mm - ref_radius_mm, cy_mm - ref_radius_mm), dpi),
        mm_to_px((cx_mm + ref_radius_mm, cy_mm + ref_radius_mm), dpi),
    ]
    draw.ellipse([bbox[0][0], bbox[0][1], bbox[1][0], bbox[1][1]], fill=0)

    blob_points_mm = wobbly_ring_points(
        BLOB_CENTER_MM, BLOB_RADIUS_X_MM, BLOB_RADIUS_Y_MM, BLOB_WOBBLE_AMPLITUDE, rng
    )
    blob_points_px = [mm_to_px(p, dpi) for p in blob_points_mm]
    draw.polygon(blob_points_px, fill=0)

    if with_hole:
        hole_points_mm = wobbly_ring_points(
            BLOB_CENTER_MM, HOLE_RADIUS_X_MM, HOLE_RADIUS_Y_MM, HOLE_WOBBLE_AMPLITUDE, rng
        )
        hole_points_px = [mm_to_px(p, dpi) for p in hole_points_mm]
        draw.polygon(hole_points_px, fill=255)

    if noise:
        arr = np.array(img).astype(np.float32)
        arr += rng.normal(0.0, 8.0, size=arr.shape)
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr, mode="L")

    return img


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("tests/fixtures/synthetic_scan.png"))
    parser.add_argument("--dpi", type=float, default=200.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--with-hole", action="store_true", default=True)
    parser.add_argument("--no-hole", dest="with_hole", action="store_false")
    parser.add_argument("--noise", action="store_true", default=False)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    img = render(args.dpi, args.seed, args.with_hole, args.noise)
    img.save(args.out)
    print(f"wrote {args.out} ({img.width}x{img.height}px @ {args.dpi}dpi)")
    print(f"  ground-truth ref circle diameter: {REF_CIRCLE_DIAMETER_MM}mm")
    print(f"  blob bbox: ~{2*BLOB_RADIUS_X_MM:.0f}mm x {2*BLOB_RADIUS_Y_MM:.0f}mm")


if __name__ == "__main__":
    main()
