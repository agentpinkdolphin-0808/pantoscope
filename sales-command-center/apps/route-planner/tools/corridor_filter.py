import math

MILES_PER_DEGREE_LAT = 69.0


def filter_by_corridor(
    candidates: list,
    route_coords: list,     # [[lon, lat], ...] GeoJSON order
    corridor_miles: float,
) -> list:
    """
    Filters candidates to those within corridor_miles of the route polyline.
    Annotates each with distance_off_route_miles and route_position_t (0.0–1.0).
    Returns sorted ascending by route_position_t (drive order).
    """
    results = []
    for c in candidates:
        dist, t = _point_to_polyline(c["lat"], c["lon"], route_coords)
        if dist <= corridor_miles:
            c = dict(c)
            c["distance_off_route_miles"] = round(dist, 2)
            c["route_position_t"] = round(t, 4)
            results.append(c)
    results.sort(key=lambda x: x["route_position_t"])
    return results


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _point_to_segment(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> tuple:
    """
    Returns (distance_miles, t_on_segment) where t_on_segment is 0..1.
    Uses equirectangular projection for the dot product — accurate enough
    for US-scale corridor filtering (error < 0.1% over 500mi routes).
    """
    # Scale lon differences by cos(lat) so units are comparable
    cos_lat = math.cos(math.radians((ay + by) / 2))
    dx, dy = (bx - ax) * cos_lat, by - ay
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq == 0:
        # Degenerate segment (a == b): distance to the point
        return _haversine_miles(py, px, ay, ax), 0.0

    # Project point onto segment
    t = ((px - ax) * cos_lat * dx + (py - ay) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))

    # Closest point on segment
    cx = ax + t * (bx - ax)
    cy = ay + t * (by - ay)
    return _haversine_miles(py, px, cy, cx), t


def _point_to_polyline(lat: float, lon: float, route_coords: list) -> tuple:
    """
    Returns (min_distance_miles, t_along_route) where t is 0.0–1.0.
    Computes cumulative arc length to assign consistent t values.
    """
    seg_lengths = []
    for i in range(len(route_coords) - 1):
        a = route_coords[i]
        b = route_coords[i + 1]
        seg_lengths.append(_haversine_miles(a[1], a[0], b[1], b[0]))

    total_length = sum(seg_lengths)
    if total_length == 0:
        return _haversine_miles(lat, lon, route_coords[0][1], route_coords[0][0]), 0.0

    best_dist = float("inf")
    best_t = 0.0
    cumulative = 0.0

    for i, seg_len in enumerate(seg_lengths):
        a = route_coords[i]
        b = route_coords[i + 1]
        dist, t_seg = _point_to_segment(lon, lat, a[0], a[1], b[0], b[1])
        if dist < best_dist:
            best_dist = dist
            # Global t: fraction of total route length at the closest point
            best_t = (cumulative + t_seg * seg_len) / total_length
        cumulative += seg_len

    return best_dist, best_t
