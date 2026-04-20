import math
import time
CRUISE = 3.0
AVOID_SPD = 1.5
DEFAULT_ALT = 10.0
CMD_GAP = 0.2
def hdg_to_vel(heading_deg, speed):
    rad = math.radians(heading_deg)
    return speed * math.cos(rad), speed * math.sin(rad)
class NavigationController:
    def __init__(self, mav, cruise_speed=CRUISE):
        self.mav = mav
        self.cruise_speed = cruise_speed
        self._t_cmd = 0.0
    def execute_decision(self, decision):
        action = decision.get("action", "HOVER")
        hdg = decision.get("safe_heading")
        if action == "NAVIGATE":
            return self._fly(hdg, self.cruise_speed)
        elif action == "AVOID":
            return self._fly(hdg, AVOID_SPD)
        elif action == "HOVER":
            return self._hover()
        elif action == "STOP":
            return self._estop()
        return False
    def go_to_waypoint(self, lat, lon, alt=DEFAULT_ALT):
        return self.mav.send_waypoint(lat, lon, alt)
    def return_to_home(self, home_lat, home_lon):
        return self.go_to_waypoint(home_lat, home_lon, DEFAULT_ALT)
    def _fly(self, hdg, speed):
        if hdg is None:
            return self._hover()
        now = time.time()
        if now - self._t_cmd < CMD_GAP:
            return True
        vx, vy = hdg_to_vel(hdg, speed)
        ok = self.mav.set_velocity(vx, vy, 0.0)
        if ok:
            self._t_cmd = now
        return ok
    def _hover(self):
        return self.mav.set_velocity(0.0, 0.0, 0.0)
    def _estop(self):
        return self.mav.set_velocity(0.0, 0.0, 0.0)
