"""Small geometry helpers working in pixel coordinates."""
from datetime import datetime, time as dtime

Box = tuple[float, float, float, float]  # x1, y1, x2, y2
Point = tuple[float, float]


def point_in_polygon(pt: Point, poly: list[Point]) -> bool:
    x, y = pt
    inside = False
    n = len(poly)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def polygon_area(poly: list[Point]) -> float:
    a = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def box_area(b: Box) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def intersection(a: Box, b: Box) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def iou(a: Box, b: Box) -> float:
    inter = intersection(a, b)
    union = box_area(a) + box_area(b) - inter
    return inter / union if union > 0 else 0.0


def center(b: Box) -> Point:
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def foot(b: Box) -> Point:
    """Bottom-centre of a box: where a person or vehicle touches the ground."""
    return ((b[0] + b[2]) / 2, b[3])


def dist(p: Point, q: Point) -> float:
    return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5


def expand(b: Box, fx: float, fy: float | None = None) -> Box:
    fy = fx if fy is None else fy
    w, h = b[2] - b[0], b[3] - b[1]
    return (b[0] - w * fx, b[1] - h * fy, b[2] + w * fx, b[3] + h * fy)


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segment_intersection(p1: Point, p2: Point, q1: Point, q2: Point) -> float | None:
    """If segment p1->p2 crosses q1-q2, return the fraction t along p1->p2 where it crosses."""
    d1, d2 = _orient(q1, q2, p1), _orient(q1, q2, p2)
    d3, d4 = _orient(p1, p2, q1), _orient(p1, p2, q2)
    if (d1 > 0) == (d2 > 0) or (d3 > 0) == (d4 > 0) or d1 == d2:
        return None
    return d1 / (d1 - d2)


def denorm(points, w: int, h: int) -> list[Point]:
    return [(float(x) * w, float(y) * h) for x, y in points]


def parse_hhmm(s: str) -> dtime:
    hh, mm = s.split(":")
    return dtime(int(hh), int(mm))


def in_time_window(now: datetime, start: str, end: str) -> bool:
    """True if now's local time is within [start, end); handles windows crossing midnight."""
    t = now.time()
    a, b = parse_hhmm(start), parse_hhmm(end)
    if a <= b:
        return a <= t < b
    return t >= a or t < b
