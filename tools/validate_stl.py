"""Sanity-check a generated STL: watertight, plausible dimensions/volume."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import trimesh


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stl_path", type=Path)
    parser.add_argument("--expect-z-height", type=float, default=None, help="expected max Z extent in mm")
    args = parser.parse_args()

    mesh = trimesh.load(str(args.stl_path))
    print(f"file: {args.stl_path}")
    print(f"watertight: {mesh.is_watertight}")
    print(f"volume: {mesh.volume:.2f} mm^3")
    print(f"bounds (mm): {mesh.bounds.tolist()}")
    dims = mesh.extents
    print(f"dimensions (mm): x={dims[0]:.2f} y={dims[1]:.2f} z={dims[2]:.2f}")

    ok = True
    if not mesh.is_watertight:
        print("FAIL: mesh is not watertight")
        ok = False
    if mesh.volume <= 0:
        print("FAIL: non-positive volume")
        ok = False
    if args.expect_z_height is not None and abs(dims[2] - args.expect_z_height) > 0.05:
        print(f"FAIL: z height {dims[2]:.3f} does not match expected {args.expect_z_height}")
        ok = False

    if ok:
        print("OK")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
