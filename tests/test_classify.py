import pytest
from shapely.geometry import Point, Polygon

from stage1_svg.classify import circularity, classify


def test_circularity_of_circle_is_near_one():
    circle = Point(0, 0).buffer(10, quad_segs=256)
    assert circularity(circle) > 0.999


def test_circularity_of_star_is_low():
    import math

    pts = []
    for i in range(10):
        r = 10 if i % 2 == 0 else 3
        angle = math.radians(36 * i)
        pts.append((r * math.cos(angle), r * math.sin(angle)))
    star = Polygon(pts)
    assert circularity(star) < 0.5


def test_classify_picks_more_circular_as_reference():
    circle = Point(0, 0).buffer(5, quad_segs=64)
    blob = Polygon([(0, 0), (20, 0), (25, 10), (15, 25), (0, 15)])
    ref, keyring = classify([blob, circle])
    assert ref.equals(circle)
    assert keyring.equals(blob)


def test_classify_requires_exactly_two_regions():
    circle = Point(0, 0).buffer(5)
    with pytest.raises(ValueError):
        classify([circle])
