from typing import Any, Dict, List, Optional, Tuple
OBSTACLE_AVOID_DISTANCE_M: float = 2.0   
OBSTACLE_STOP_DISTANCE_M: float = 0.5    
MIN_VALID_DISTANCE_MM: int = 100          
MAX_VALID_DISTANCE_MM: int = 12_000       
def filter_points(points: List[Dict]) -> List[Dict]:
    return [
        pt for pt in points
        if MIN_VALID_DISTANCE_MM <= pt.get("distance_mm", 0) <= MAX_VALID_DISTANCE_MM
        and pt.get("intensity", 0) > 10
    ]
def build_distance_map(
    points: List[Dict],
    resolution_deg: float = 5.0,
) -> Dict[float, Optional[float]]:
    num_buckets = int(360.0 / resolution_deg)
    distance_map: Dict[float, float] = {
        i * resolution_deg: float("inf") for i in range(num_buckets)
    }
    for pt in points:
        distance_mm = pt.get("distance_mm", 0)
        if distance_mm == 0:
            continue
        angle = pt.get("angle", 0.0)
        bucket = round(angle / resolution_deg) * resolution_deg % 360.0
        distance_m = distance_mm / 1000.0
        if distance_m < distance_map[bucket]:
            distance_map[bucket] = distance_m
    return {
        angle: (dist if dist != float("inf") else None)
        for angle, dist in distance_map.items()
    }
def detect_obstacles(distance_map: Dict[float, Optional[float]]) -> List[Dict]:
    obstacles = []
    for angle, distance in distance_map.items():
        if distance is None or distance >= OBSTACLE_AVOID_DISTANCE_M:
            continue
        if distance < OBSTACLE_STOP_DISTANCE_M:
            severity = "critical"
        elif distance < 1.0:
            severity = "warning"
        else:
            severity = "caution"
        obstacles.append({
            "angle_deg": angle,
            "distance_m": round(distance, 3),
            "severity": severity,
        })
    return sorted(obstacles, key=lambda x: x["distance_m"])
def find_safe_heading(
    distance_map: Dict[float, Optional[float]],
    preferred_heading: float = 0.0,
    clearance_m: float = OBSTACLE_AVOID_DISTANCE_M,
) -> Tuple[Optional[float], str]:
    candidates = []
    for angle, distance in distance_map.items():
        if distance is None or distance >= clearance_m:
            delta = abs(angle - preferred_heading)
            if delta > 180:
                delta = 360 - delta
            candidates.append((angle, delta))
    if not candidates:
        return None, "all_blocked"
    candidates.sort(key=lambda x: x[1])
    best_angle, best_delta = candidates[0]
    reason = "clear" if best_delta < 1.0 else "diverted"
    return best_angle, reason
def classify_terrain(distance_map: Dict[float, Optional[float]]) -> str:
    readings = [d for d in distance_map.values() if d is not None]
    if not readings:
        return "unknown"
    close_count = sum(1 for d in readings if d < OBSTACLE_AVOID_DISTANCE_M)
    density = close_count / len(readings)
    if density > 0.70:
        return "blocked"
    if density > 0.40:
        return "cluttered"
    if density > 0.10:
        return "corridor"
    return "open"
def process_scan(raw_scan: Dict[str, Any]) -> Dict[str, Any]:
    if raw_scan is None:
        return {
            "error": "no_scan_data",
            "obstacles": [],
            "distance_map": {},
            "terrain_class": "unknown",
        }
    points = raw_scan.get("points", [])
    filtered = filter_points(points)
    distance_map = build_distance_map(filtered)
    obstacles = detect_obstacles(distance_map)
    terrain = classify_terrain(distance_map)
    return {
        "timestamp": raw_scan.get("timestamp"),
        "raw_point_count": len(points),
        "filtered_point_count": len(filtered),
        "distance_map": distance_map,
        "obstacles": obstacles,
        "obstacle_count": len(obstacles),
        "terrain_class": terrain,
    }
def process_tf_luna(reading: Optional[Dict]) -> Dict[str, Any]:
    if reading is None or not reading.get("valid"):
        return {"obstacle_ahead": False, "distance_m": None, "severity": "none", "valid": False}
    distance = reading["distance_m"]
    if distance < OBSTACLE_STOP_DISTANCE_M:
        severity = "critical"
    elif distance < 1.0:
        severity = "warning"
    elif distance < OBSTACLE_AVOID_DISTANCE_M:
        severity = "caution"
    else:
        severity = "none"
    return {
        "obstacle_ahead": distance < OBSTACLE_AVOID_DISTANCE_M,
        "distance_m": distance,
        "severity": severity,
        "valid": True,
    }
