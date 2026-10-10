"""Point-in-polygon check for the campus geofence (polygon of [lat, lon] points)."""


def point_in_polygon(lat: float, lon: float, polygon: list[list[float]]) -> bool:
    """Ray-casting test. Works for simple (non self-intersecting) polygons."""
    if not polygon or len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i][0], polygon[i][1]
        yj, xj = polygon[j][0], polygon[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def validate_polygon(polygon) -> list[list[float]]:
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("Geofence needs at least 3 points")
    out = []
    for pt in polygon:
        lat, lon = float(pt[0]), float(pt[1])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Invalid coordinate")
        out.append([lat, lon])
    return out
