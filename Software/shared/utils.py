import math
import time
import json
def haversine(lat1, lon1, lat2, lon2):
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
def bearing_between(lat1, lon1, lat2, lon2):
    a1, a2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(a2)
    y = math.cos(a1) * math.sin(a2) - math.sin(a1) * math.cos(a2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360
def offset_coordinate(lat, lon, distance_m, bearing_deg):
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
def normalize_angle(angle_deg):
    return angle_deg % 360
def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))
def format_gps(gps):
    if not gps:
        return "GPS: unavailable"
    return (
        f"GPS: ({gps.get('lat', 0):.6f}, {gps.get('lon', 0):.6f}) "
        f"fix={gps.get('fix_type', 0)} sats={gps.get('satellites_visible', 0)}"
    )
def safe_json(data):
    def _fix(obj):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj
    return json.dumps(data, default=_fix)
def timestamp_ms():
    return int(time.time() * 1000)
