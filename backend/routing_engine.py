import math
import logging
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx
from flood_model import FloodModel
logger = logging.getLogger(__name__)
SAFETY_MULTIPLIER: float = 10.0
BLOCKED_WEIGHT: float = float("inf")
class RoutingEngine:
    def __init__(self, flood_model: Optional[FloodModel] = None) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()
        self.flood_model: FloodModel = flood_model or FloodModel()
        self._coords: Dict[str, Tuple[float, float]] = {}
    def add_node(
        self,
        node_id: str,
        lat: float,
        lon: float,
        elevation_m: float = 0.0,
        label: str = "",
    ) -> None:
        self.graph.add_node(node_id, lat=lat, lon=lon, elevation=elevation_m, label=label)
        self._coords[node_id] = (lat, lon)
        self.flood_model.set_node_elevation(node_id, elevation_m)
        logger.debug(f"Node: {node_id!r} ({lat:.5f}, {lon:.5f}) elev={elevation_m} m")
    def add_road(
        self,
        from_id: str,
        to_id: str,
        bidirectional: bool = True,
        blocked: bool = False,
    ) -> None:
        if from_id not in self.graph or to_id not in self.graph:
            logger.warning(f"add_road: node {from_id!r} or {to_id!r} not found")
            return
        weight = BLOCKED_WEIGHT if blocked else self._edge_weight(from_id, to_id)
        self.graph.add_edge(from_id, to_id, weight=weight, blocked=blocked)
        if bidirectional:
            self.graph.add_edge(to_id, from_id, weight=weight, blocked=blocked)
        logger.debug(
            f"Road: {from_id} {'↔' if bidirectional else '→'} {to_id}  "
            f"w={weight:.1f}  blocked={blocked}"
        )
    def find_safest_route(
        self,
        origin_id: str,
        destination_id: str,
    ) -> Optional[Dict[str, Any]]:
        for nid in (origin_id, destination_id):
            if nid not in self.graph:
                logger.error(f"find_safest_route: node {nid!r} not in graph")
                return None
        try:
            path: List[str] = nx.dijkstra_path(
                self.graph, origin_id, destination_id, weight="weight"
            )
            total_weight: float = nx.dijkstra_path_length(
                self.graph, origin_id, destination_id, weight="weight"
            )
        except nx.NetworkXNoPath:
            logger.warning(f"No path found: {origin_id!r} → {destination_id!r}")
            return None
        except nx.NodeNotFound as exc:
            logger.error(f"find_safest_route NodeNotFound: {exc}")
            return None
        waypoints = []
        total_dist = 0.0
        max_risk = 0.0
        for i, nid in enumerate(path):
            lat, lon = self._coords[nid]
            node_data = self.graph.nodes[nid]
            risk = self.flood_model.get_point_risk(lat, lon)
            max_risk = max(max_risk, risk)
            waypoints.append({
                "node_id": nid,
                "lat": lat,
                "lon": lon,
                "elevation_m": node_data.get("elevation", 0.0),
                "label": node_data.get("label", ""),
                "flood_risk": risk,
            })
            if i > 0:
                prev_lat, prev_lon = self._coords[path[i - 1]]
                total_dist += self._haversine(prev_lat, prev_lon, lat, lon)
        return {
            "origin": origin_id,
            "destination": destination_id,
            "path": path,
            "waypoints": waypoints,
            "total_distance_m": round(total_dist, 1),
            "total_weight": round(total_weight, 2),
            "max_flood_risk": round(max_risk, 3),
            "hop_count": len(path) - 1,
        }
    def block_road(self, from_id: str, to_id: str, bidirectional: bool = True) -> None:
        pairs = [(from_id, to_id)]
        if bidirectional:
            pairs.append((to_id, from_id))
        for u, v in pairs:
            if self.graph.has_edge(u, v):
                self.graph[u][v]["weight"] = BLOCKED_WEIGHT
                self.graph[u][v]["blocked"] = True
        logger.info(f"Road blocked: {from_id} ↔ {to_id}")
    def unblock_road(self, from_id: str, to_id: str, bidirectional: bool = True) -> None:
        pairs = [(from_id, to_id)]
        if bidirectional:
            pairs.append((to_id, from_id))
        for u, v in pairs:
            if self.graph.has_edge(u, v):
                self.graph[u][v]["weight"] = self._edge_weight(u, v)
                self.graph[u][v]["blocked"] = False
        logger.info(f"Road unblocked: {from_id} ↔ {to_id}")
    def refresh_edge_weights(self, node_id: str) -> None:
        for u, v in list(self.graph.out_edges(node_id)) + list(self.graph.in_edges(node_id)):
            if not self.graph[u][v].get("blocked", False):
                self.graph[u][v]["weight"] = self._edge_weight(u, v)
    def graph_info(self) -> Dict[str, Any]:
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "nodes": list(self.graph.nodes),
            "is_connected": (
                nx.is_weakly_connected(self.graph)
                if self.graph.number_of_nodes() > 0
                else False
            ),
        }
    def _edge_weight(self, from_id: str, to_id: str) -> float:
        coord_a = self._coords[from_id]
        coord_b = self._coords[to_id]
        dist_m = self._haversine(*coord_a, *coord_b)
        risk = self.flood_model.get_edge_risk(
            coord_a, coord_b, node_a_id=from_id, node_b_id=to_id
        )
        return round(dist_m * (1.0 + SAFETY_MULTIPLIER * risk), 2)
    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
