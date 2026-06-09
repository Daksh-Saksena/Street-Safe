import math
import random
import time
_t0 = time.time()
def _elapsed():
    return time.time() - _t0
_lat = None
_lon = None
_speed = 2.0
def set_position(lat, lon):
    global _lat, _lon
    _lat = lat
    _lon = lon
    print(f"[MOCK] GPS pinned → ({lat:.6f}, {lon:.6f})")
def set_speed(speed):
    global _speed
    if abs(speed - _speed) > 0.05:
        _speed = speed
        print(f"[MOCK] Speed → {speed:.1f} m/s")
class MockMAVLinkInterface:
    def __init__(self):
        self._armed = False
        self._mode = "GUIDED"
        self._vx = 0.0
        self._vy = 0.0
    def connect(self):
        print("[MOCK] MAVLink: connected to simulated flight controller")
        return True
    def is_connected(self):
        return True
    def update_heartbeat(self):
        pass
    def disconnect(self):
        print("[MOCK] MAVLink: disconnected")
    def get_gps(self):
        t = _elapsed()
        if _lat is not None and _lon is not None:
            return {
                "lat": round(_lat + random.uniform(-0.000003, 0.000003), 7),
                "lon": round(_lon + random.uniform(-0.000003, 0.000003), 7),
                "alt_msl": round(50.0 + math.sin(t * 0.1) * 0.3, 2),
                "fix_type": 3,
                "satellites_visible": random.randint(9, 14),
            }
        spd = max(_speed, 0.1)
        lat = 28.6139 + (self._vx * t * 0.000009 * spd / 2.0)
        lon = 77.2090 + (self._vy * t * 0.000009 * spd / 2.0)
        return {
            "lat": round(lat + random.uniform(-0.000005, 0.000005), 7),
            "lon": round(lon + random.uniform(-0.000005, 0.000005), 7),
            "alt_msl": round(50.0 + math.sin(t * 0.1) * 0.3, 2),
            "fix_type": 3,
            "satellites_visible": random.randint(9, 14),
        }
    def get_altitude(self):
        t = _elapsed()
        return {
            "alt_relative": round(10.0 + math.sin(t * 0.2) * 0.2, 2),
            "groundspeed": round(_speed, 2),
            "airspeed": round(_speed + 0.3, 2),
            "heading": round((math.degrees(math.atan2(self._vy, self._vx)) + 360) % 360, 1),
            "throttle": 55,
        }
    def get_attitude(self):
        t = _elapsed()
        return {
            "roll": round(math.sin(t * 0.5) * 3.0, 2),
            "pitch": round(math.cos(t * 0.3) * 2.0, 2),
            "yaw": 0.0,
            "rollspeed": 0.0,
            "pitchspeed": 0.0,
            "yawspeed": 0.0,
        }
    def send_waypoint(self, lat, lon, alt):
        print(f"[MOCK] MAVLink: waypoint set → ({lat:.6f}, {lon:.6f}) alt={alt} m")
        return True
    def set_velocity(self, vx, vy, vz):
        self._vx = vx
        self._vy = vy
        return True
    def set_guided_mode(self):
        self._mode = "GUIDED"
        return True
    def arm(self):
        self._armed = True
        print("[MOCK] MAVLink: motors ARMED")
        return True
_SCENARIOS = {
    "clear":     [],
    "obstacle":  [(0, 1.2), (345, 1.5), (15, 1.8)],
    "emergency": [(0, 0.3), (350, 0.4), (10, 0.35)],
}
_CURRENT_SCENARIO = "clear"
class MockSensorManager:
    def __init__(self):
        pass
    def initialize(self):
        print("[MOCK] Sensors: D500 + TF-Luna simulated and ready")
        return {"d500": True, "tf_luna": True}
    @staticmethod
    def set_scenario(name):
        global _CURRENT_SCENARIO
        if name not in _SCENARIOS:
            raise ValueError(f"Unknown scenario {name!r}. Choose from {list(_SCENARIOS)}")
        if _CURRENT_SCENARIO != name:
            _CURRENT_SCENARIO = name
            print(f"[MOCK] Scenario → {name.upper()}")
    @staticmethod
    def _make_d500_scan():
        injected = {angle: dist for angle, dist in _SCENARIOS[_CURRENT_SCENARIO]}
        pts = []
        for deg in range(360):
            dm = 8.0
            for obs_angle, obs_dist in injected.items():
                if abs(deg - obs_angle) <= 10 or abs(deg - obs_angle - 360) <= 10:
                    dm = obs_dist + random.uniform(-0.05, 0.05)
                    break
            pts.append({
                "angle": float(deg),
                "distance_mm": int(dm * 1000),
                "intensity": random.randint(150, 255) if dm < 7 else random.randint(20, 80),
            })
        return {
            "sensor": "ldrobot_d500",
            "timestamp": time.time(),
            "frame_count": 30,
            "point_count": len(pts),
            "points": pts,
        }
    @staticmethod
    def _make_tf_luna():
        frontal = None
        for angle, dist in _SCENARIOS[_CURRENT_SCENARIO]:
            if abs(angle) <= 15:
                frontal = dist
                break
        d = (frontal if frontal else 8.0) + random.uniform(-0.02, 0.02)
        return {
            "sensor": "tf_luna",
            "timestamp": time.time(),
            "distance_cm": int(d * 100),
            "distance_m": round(d, 3),
            "amplitude": 2500,
            "chip_temp_c": round(35.0 + random.uniform(-0.5, 0.5), 1),
            "valid": True,
        }
    def read_lidar(self):
        return self._make_d500_scan()
    def read_tf_luna(self):
        return self._make_tf_luna()
    def read_all(self):
        return {"lidar_360": self.read_lidar(), "lidar_front": self.read_tf_luna(), "timestamp": time.time()}
    def shutdown(self):
        print("[MOCK] Sensors: shutdown")
