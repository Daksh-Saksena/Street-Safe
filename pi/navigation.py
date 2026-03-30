import math
import time
import logging
from typing import Any, Dict, Optional, Tuple
from mavlink_interface import MAVLinkInterface
logger = logging.getLogger(__name__)
CRUISE_SPEED_MS: float = 3.0     
AVOIDANCE_SPEED_MS: float = 1.5  
DEFAULT_ALTITUDE_M: float = 10.0 
COMMAND_INTERVAL_S: float = 0.2
def heading_to_ned_velocity(heading_deg: float, speed_ms: float) -> Tuple[float, float]:
    rad = math.radians(heading_deg)
    vx = speed_ms * math.cos(rad)  
    vy = speed_ms * math.sin(rad)  
    return vx, vy
class NavigationController:
    def __init__(self, mav: MAVLinkInterface, cruise_speed: float = CRUISE_SPEED_MS) -> None:
        self.mav = mav
        self.cruise_speed = cruise_speed
        self._last_command_time: float = 0.0
    def execute_decision(self, decision: Dict[str, Any]) -> bool:
        action = decision.get("action", "HOVER")
        safe_heading = decision.get("safe_heading")
        if action == "NAVIGATE":
            return self._fly_heading(safe_heading, self.cruise_speed)
        elif action == "AVOID":
            return self._fly_heading(safe_heading, AVOIDANCE_SPEED_MS)
        elif action == "HOVER":
            return self._hover()
        elif action == "STOP":
            return self._emergency_stop()
        else:
            logger.warning(f"execute_decision: unknown action '{action}'")
            return False
    def go_to_waypoint(self, lat: float, lon: float, alt: float = DEFAULT_ALTITUDE_M) -> bool:
        logger.info(f"Waypoint: ({lat:.6f}, {lon:.6f}) alt={alt} m")
        return self.mav.send_waypoint(lat, lon, alt)
    def return_to_home(self, home_lat: float, home_lon: float) -> bool:
        logger.info("Return-to-home initiated")
        return self.go_to_waypoint(home_lat, home_lon, DEFAULT_ALTITUDE_M)
    def _fly_heading(self, heading_deg: Optional[float], speed_ms: float) -> bool:
        if heading_deg is None:
            return self._hover()
        now = time.time()
        if now - self._last_command_time < COMMAND_INTERVAL_S:
            return True
        vx, vy = heading_to_ned_velocity(heading_deg, speed_ms)
        success = self.mav.set_velocity(vx, vy, 0.0)  
        if success:
            self._last_command_time = now
            logger.debug(
                f"Fly heading={heading_deg:.1f}° speed={speed_ms} m/s "
                f"(vx={vx:.2f}, vy={vy:.2f})"
            )
        return success
    def _hover(self) -> bool:
        logger.info("Holding hover")
        return self.mav.set_velocity(0.0, 0.0, 0.0)
    def _emergency_stop(self) -> bool:
        logger.warning("EMERGENCY STOP — zeroing all velocity")
        return self.mav.set_velocity(0.0, 0.0, 0.0)
