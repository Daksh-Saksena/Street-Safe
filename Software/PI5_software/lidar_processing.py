OBSTACLE_AVOID_DISTANCE_M = 2.0
OBSTACLE_STOP_DISTANCE_M = 0.5
MIN_VALID_DISTANCE_MM = 100
MAX_VALID_DISTANCE_MM = 12_000
def filter_points(points):
    return [
        pt for pt in points
        if MIN_VALID_DISTANCE_MM <= pt.get("distance_mm", 0) <= MAX_VALID_DISTANCE_MM
        and pt.get("intensity", 0) > 10
    ]
def build_distance_map(points, res=5.0):
    n = int(360.0 / res)
    dmap = {i * res: float("inf") for i in range(n)}
    for pt in points:
        dmm = pt.get("distance_mm", 0)
        if dmm == 0:
            continue
        bucket = round(pt.get("angle", 0.0) / res) * res % 360.0
        dm = dmm / 1000.0
        if dm < dmap[bucket]:
            dmap[bucket] = dm
    return {a: (d if d != float("inf") else None) for a, d in dmap.items()}
def detect_obstacles(dmap):
    obs = []
    for angle, dist in dmap.items():
        if dist is None or dist >= OBSTACLE_AVOID_DISTANCE_M:
            continue
        if dist < OBSTACLE_STOP_DISTANCE_M:
            sev = "critical"
        elif dist < 1.0:
            sev = "warning"
        else:
            sev = "caution"
        obs.append({"angle_deg": angle, "distance_m": round(dist, 3), "severity": sev})
    return sorted(obs, key=lambda x: x["distance_m"])
def find_safe_heading(dmap, preferred_heading=0.0, clearance_m=OBSTACLE_AVOID_DISTANCE_M):
    candidates = []
    for angle, dist in dmap.items():
        if dist is None or dist >= clearance_m:
            delta = abs(angle - preferred_heading)
            if delta > 180:
                delta = 360 - delta
            candidates.append((angle, delta))
    if not candidates:
        return None, "all_blocked"
    candidates.sort(key=lambda x: x[1])
    a, d = candidates[0]
    return a, ("clear" if d < 1.0 else "diverted")
def classify_terrain(dmap):
    readings = [d for d in dmap.values() if d is not None]
    if not readings:
        return "unknown"
    close = sum(1 for d in readings if d < OBSTACLE_AVOID_DISTANCE_M)
    density = close / len(readings)
    if density > 0.70:
        return "blocked"
    if density > 0.40:
        return "cluttered"
    if density > 0.10:
        return "corridor"
    return "open"
def process_scan(raw_scan):
    if raw_scan is None:
        return {"error": "no_scan_data", "obstacles": [], "distance_map": {}, "terrain_class": "unknown"}
    points = raw_scan.get("points", [])
    pts = filter_points(points)
    dmap = build_distance_map(pts)
    obs = detect_obstacles(dmap)
    terrain = classify_terrain(dmap)
    return {
        "timestamp": raw_scan.get("timestamp"),
        "raw_point_count": len(points),
        "filtered_point_count": len(pts),
        "distance_map": dmap,
        "obstacles": obs,
        "obstacle_count": len(obs),
        "terrain_class": terrain,
    }
def process_tf_luna(reading):
    if reading is None or not reading.get("valid"):
        return {"obstacle_ahead": False, "distance_m": None, "severity": "none", "valid": False}
    d = reading["distance_m"]
    if d < OBSTACLE_STOP_DISTANCE_M:
        sev = "critical"
    elif d < 1.0:
        sev = "warning"
    elif d < OBSTACLE_AVOID_DISTANCE_M:
        sev = "caution"
    else:
        sev = "none"
    return {"obstacle_ahead": d < OBSTACLE_AVOID_DISTANCE_M, "distance_m": d, "severity": sev, "valid": True}
