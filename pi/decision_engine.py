import time
import logging
from typing import Any, Dict, List, Optional
from lidar_processing import (
    find_safe_heading,
    OBSTACLE_AVOID_DISTANCE_M,
    OBSTACLE_STOP_DISTANCE_M,
)
logger = logging.getLogger(__name__)
ALERT_NONE = "none"
ALERT_CAUTION = "caution"
ALERT_WARNING = "warning"
ALERT_CRITICAL = "critical"
MIN_ACCEPTABLE_FIX = 2
MIN_ALTITUDE_M = 1.5
class DecisionEngine:
    VALID_STATES = ("NAVIGATING", "AVOIDING", "HOVERING", "EMERGENCY")
    def __init__(self, target_heading: float = 0.0) -> None:
        self.target_heading: float = target_heading  
        self.state: str = "NAVIGATING"
        self._alerts: List[Dict] = []
    def update_target(self, heading: float) -> None:
        self.target_heading = heading
    def _alert(self, level: str, message: str, data: Optional[Dict] = None) -> Dict:
        entry = {
            "level": level,
            "message": message,
            "timestamp": time.time(),
            "data": data or {},
        }
        self._alerts.append(entry)
        if level in (ALERT_WARNING, ALERT_CRITICAL):
            logger.warning(f"[{level.upper()}] {message}")
        return entry
    def evaluate(
        self,
        processed_scan: Dict[str, Any],
        tf_luna_data: Optional[Dict],
        gps_data: Optional[Dict],
        altitude_data: Optional[Dict],
    ) -> Dict[str, Any]:
        self._alerts = []
        obstacles = processed_scan.get("obstacles", [])
        distance_map = processed_scan.get("distance_map", {})
        terrain = processed_scan.get("terrain_class", "unknown")
        frontal_critical = False
        if tf_luna_data and tf_luna_data.get("valid"):
            frontal_dist: Optional[float] = tf_luna_data.get("distance_m")
            if frontal_dist is not None and frontal_dist < OBSTACLE_STOP_DISTANCE_M:
                self._alert(
                    ALERT_CRITICAL,
                    f"Frontal obstacle at {frontal_dist:.2f} m — EMERGENCY STOP",
                    tf_luna_data,
                )
                frontal_critical = True
        if altitude_data:
            alt_agl: float = altitude_data.get("alt_relative", 0.0)
            if alt_agl < MIN_ALTITUDE_M:
                self._alert(ALERT_WARNING, f"Altitude too low: {alt_agl:.1f} m AGL")
        if gps_data:
            fix: int = gps_data.get("fix_type", 0)
            if fix < MIN_ACCEPTABLE_FIX:
                self._alert(ALERT_WARNING, f"Poor GPS fix (type={fix})", gps_data)
        safe_heading, heading_reason = find_safe_heading(
            distance_map,
            preferred_heading=self.target_heading,
            clearance_m=OBSTACLE_AVOID_DISTANCE_M,
        )
        if frontal_critical:
            self.state = "EMERGENCY"
            action = "STOP"
        elif terrain == "blocked":
            self.state = "HOVERING"
            action = "HOVER"
            self._alert(ALERT_WARNING, "All directions blocked — holding position")
        elif safe_heading is None:
            self.state = "HOVERING"
            action = "HOVER"
            self._alert(ALERT_WARNING, "No clear heading found — holding position")
        elif obstacles and safe_heading != self.target_heading:
            self.state = "AVOIDING"
            action = "AVOID"
            self._alert(
                ALERT_CAUTION,
                f"Obstacle divert: {self.target_heading:.0f}° → {safe_heading:.0f}°",
            )
        else:
            self.state = "NAVIGATING"
            action = "NAVIGATE"
        return {
            "state": self.state,
            "action": action,
            "safe_heading": safe_heading,
            "target_heading": self.target_heading,
            "terrain_class": terrain,
            "obstacles": obstacles,          
            "obstacle_count": len(obstacles),
            "alerts": list(self._alerts),
            "reason": heading_reason,
            "timestamp": time.time(),
        }
