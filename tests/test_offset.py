import math

from shapely.geometry import Point

from stage1_svg.offset import make_base_polygon


def test_offset_area_matches_expanded_circle():
    r = 20.0
    d = 1.5
    circle = Point(0, 0).buffer(r, quad_segs=256)
    base = make_base_polygon(circle, offset_mm=d)
    expected_area = math.pi * (r + d) ** 2
    assert abs(base.area - expected_area) / expected_area < 0.02


def test_offset_fills_holes():
    outer = Point(0, 0).buffer(20, quad_segs=64)
    hole = Point(0, 0).buffer(5, quad_segs=64)
    ring_poly = outer.difference(hole)
    assert len(ring_poly.interiors) == 1
    base = make_base_polygon(ring_poly, offset_mm=1.5)
    assert len(base.interiors) == 0
