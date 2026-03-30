import math
import logging
from typing import Dict, List, Optional, Tuple
logger = logging.getLogger(__name__)
RISK_NONE: float = 0.0
RISK_LOW: float = 0.2
RISK_MEDIUM: float = 0.5
RISK_HIGH: float = 0.8
RISK_IMPASSABLE: float = 1.0
class FloodModel:
    def __init__(self) -> None:
        self._zones: List[Tuple[float, float, float, float]] = []
        self._elevation: Dict[str, float] = {}
    def register_flood_zone(
        self,
        lat: float,
        lon: float,
        radius_m: float,
        risk: float = RISK_HIGH,
    ) -> None:
        risk = max(0.0, min(1.0, risk))
        self._zones.append((lat, lon, radius_m, risk))
        logger.info(
            f"Flood zone registered: ({lat:.5f}, {lon:.5f}) "
            f"r={radius_m} m  risk={risk}"
        )
    def set_node_elevation(self, node_id: str, elevation_m: float) -> None:
        self._elevation[node_id] = elevation_m
    def get_point_risk(self, lat: float, lon: float) -> float:
        max_risk = RISK_NONE
        for z_lat, z_lon, z_radius, z_risk in self._zones:
            dist = self._haversine(lat, lon, z_lat, z_lon)
            if dist > z_radius:
                continue
            attenuation = 1.0 - (dist / z_radius) * 0.3
            effective = z_risk * attenuation
            max_risk = max(max_risk, effective)
        return round(max_risk, 3)
    def get_edge_risk(
        self,
        coord_a: Tuple[float, float],
        coord_b: Tuple[float, float],
        node_a_id: str = "",
        node_b_id: str = "",
    ) -> float:
        risk_a = self.get_point_risk(*coord_a)
        risk_b = self.get_point_risk(*coord_b)
        segment_risk = max(risk_a, risk_b)
        elev_a = self._elevation.get(node_a_id, 0.0)
        elev_b = self._elevation.get(node_b_id, 0.0)
        avg_elevation = (elev_a + elev_b) / 2.0
        if avg_elevation < 5.0:
            elev_penalty = 0.20  
        elif avg_elevation < 15.0:
            elev_penalty = 0.10
        else:
            elev_penalty = 0.0   
        return round(min(1.0, segment_risk + elev_penalty), 3)
    def is_passable(self, lat: float, lon: float) -> bool:
        return self.get_point_risk(lat, lon) < RISK_IMPASSABLE
    def summary(self) -> Dict:
        return {
            "zone_count": len(self._zones),
            "zones": [
                {
                    "lat": lat,
                    "lon": lon,
                    "radius_m": radius,
                    "risk": risk,
                }
                for lat, lon, radius, risk in self._zones
            ],
        }
    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
