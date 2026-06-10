import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.utils import haversine
RISK_NONE = 0.0
RISK_LOW = 0.2
RISK_MEDIUM = 0.5
RISK_HIGH = 0.8
RISK_IMPASSABLE = 1.0
class FloodModel:
    def __init__(self):
        self._zones = []
        self._elevation = {}
    def register_flood_zone(self, lat, lon, radius_m, risk=RISK_HIGH):
        risk = max(0.0, min(1.0, risk))
        self._zones.append((lat, lon, radius_m, risk))
    def set_node_elevation(self, node_id, elevation_m):
        self._elevation[node_id] = elevation_m
    def get_point_risk(self, lat, lon):
        risk = RISK_NONE
        for zl, zo, zr, zk in self._zones:
            d = haversine(lat, lon, zl, zo)
            if d > zr:
                continue
            eff = zk * (1.0 - (d / zr) * 0.3)
            risk = max(risk, eff)
        return round(risk, 3)
    def get_edge_risk(self, ca, cb, node_a_id="", node_b_id=""):
        risk = max(self.get_point_risk(*ca), self.get_point_risk(*cb))
        avg_elev = (self._elevation.get(node_a_id, 0.0) + self._elevation.get(node_b_id, 0.0)) / 2.0
        if avg_elev < 5.0:
            penalty = 0.20
        elif avg_elev < 15.0:
            penalty = 0.10
        else:
            penalty = 0.0
        return round(min(1.0, risk + penalty), 3)
    def is_passable(self, lat, lon):
        return self.get_point_risk(lat, lon) < RISK_IMPASSABLE
    def summary(self):
        return {
            "zone_count": len(self._zones),
            "zones": [
                {"lat": lat, "lon": lon, "radius_m": r, "risk": risk}
                for lat, lon, r, risk in self._zones
            ],
        }
