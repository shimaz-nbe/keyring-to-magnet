from shapely.geometry import Point

from stage1_svg.calibrate import compute_scale


def test_compute_scale_known_circle():
    radius_units = 50.0
    circle = Point(0, 0).buffer(radius_units, quad_segs=256)
    scale = compute_scale(circle, known_diameter_mm=10.0)
    assert abs(scale - (10.0 / (2 * radius_units))) < 1e-3
