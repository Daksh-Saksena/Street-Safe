import time
from lidar_processing import (
    find_safe_heading,
    OBSTACLE_AVOID_DISTANCE_M,
    OBSTACLE_STOP_DISTANCE_M,
)
ALERT_NONE = "none"
ALERT_CAUTION = "caution"
ALERT_WARNING = "warning"
ALERT_CRITICAL = "critical"
MIN_FIX = 2
MIN_ALT = 1.5
class DecisionEngine:
    VALID_STATES = ("NAVIGATING", "AVOIDING", "HOVERING", "EMERGENCY")
    def __init__(self, target_heading=0.0):
        self.target_heading = target_heading
        self.state = "NAVIGATING"
        self._alerts = []
    def update_target(self, heading):
        self.target_heading = heading
    def _alert(self, level, message, data=None):
        entry = {"level": level, "message": message, "timestamp": time.time(), "data": data or {}}
        self._alerts.append(entry)
        return entry
    def evaluate(self, processed_scan, tf_luna_data, gps_data, altitude_data):
        self._alerts = []
        obstacles = processed_scan.get("obstacles", [])
        dmap = processed_scan.get("distance_map", {})
        terrain = processed_scan.get("terrain_class", "unknown")
        critical = False
        if tf_luna_data and tf_luna_data.get("valid"):
            dist = tf_luna_data.get("distance_m")
            if dist is not None and dist < OBSTACLE_STOP_DISTANCE_M:
                self._alert(ALERT_CRITICAL, f"Frontal obstacle at {dist:.2f} m — EMERGENCY STOP", tf_luna_data)
                critical = True
        if altitude_data:
            agl = altitude_data.get("alt_relative", 0.0)
            if agl < MIN_ALT:
                self._alert(ALERT_WARNING, f"Altitude too low: {agl:.1f} m AGL")
        if gps_data:
            fix = gps_data.get("fix_type", 0)
            if fix < MIN_FIX:
                self._alert(ALERT_WARNING, f"Poor GPS fix (type={fix})", gps_data)
        heading, reason = find_safe_heading(dmap, preferred_heading=self.target_heading, clearance_m=OBSTACLE_AVOID_DISTANCE_M)
        if critical:
            self.state = "EMERGENCY"
            action = "STOP"
        elif terrain == "blocked":
            self.state = "HOVERING"
            action = "HOVER"
            self._alert(ALERT_WARNING, "All directions blocked — holding position")
        elif heading is None:
            self.state = "HOVERING"
            action = "HOVER"
            self._alert(ALERT_WARNING, "No clear heading found — holding position")
        elif obstacles and heading != self.target_heading:
            self.state = "AVOIDING"
            action = "AVOID"
            self._alert(ALERT_CAUTION, f"Obstacle divert: {self.target_heading:.0f}° → {heading:.0f}°")
        else:
            self.state = "NAVIGATING"
            action = "NAVIGATE"
        return {
            "state": self.state,
            "action": action,
            "safe_heading": heading,
            "target_heading": self.target_heading,
            "terrain_class": terrain,
            "obstacles": obstacles,
            "obstacle_count": len(obstacles),
            "alerts": list(self._alerts),
            "reason": reason,
            "timestamp": time.time(),
        }
