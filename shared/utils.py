import math
import time
import json
from typing import Tuple, Dict, Any, Optional
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000  
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
def bearing_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360
def offset_coordinate(lat: float, lon: float, distance_m: float, bearing_deg: float) -> Tuple[float, float]:
    R = 6_371_000
    bearing = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance_m / R)
        + math.cos(lat1) * math.sin(distance_m / R) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(distance_m / R) * math.cos(lat1),
        math.cos(distance_m / R) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)
def normalize_angle(angle_deg: float) -> float:
    return angle_deg % 360
def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))
def format_gps(gps_data: Optional[Dict]) -> str:
    if not gps_data:
        return "GPS: unavailable"
    return (
        f"GPS: ({gps_data.get('lat', 0):.6f}, {gps_data.get('lon', 0):.6f}) "
        f"fix={gps_data.get('fix_type', 0)} sats={gps_data.get('satellites_visible', 0)}"
    )
def safe_json(data: Any) -> str:
    def _fix(obj: Any) -> Any:
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj
    return json.dumps(data, default=_fix)
def timestamp_ms() -> int:
    return int(time.time() * 1000)
