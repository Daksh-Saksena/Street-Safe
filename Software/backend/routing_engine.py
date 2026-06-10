import os
import sys
import math
import networkx as nx
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.utils import haversine
from flood_model import FloodModel
SAFETY_MULTIPLIER = 10.0
BLOCKED_WEIGHT = float("inf")
class RoutingEngine:
    def __init__(self, flood_model=None):
        self.graph = nx.DiGraph()
        self.flood_model = flood_model or FloodModel()
        self._coords = {}
    def add_node(self, node_id, lat, lon, elevation_m=0.0, label=""):
        self.graph.add_node(node_id, lat=lat, lon=lon, elevation=elevation_m, label=label)
        self._coords[node_id] = (lat, lon)
        self.flood_model.set_node_elevation(node_id, elevation_m)
    def add_road(self, from_id, to_id, bidirectional=True, blocked=False):
        if from_id not in self.graph or to_id not in self.graph:
            return
        w = BLOCKED_WEIGHT if blocked else self._edge_weight(from_id, to_id)
        self.graph.add_edge(from_id, to_id, weight=w, blocked=blocked)
        if bidirectional:
            self.graph.add_edge(to_id, from_id, weight=w, blocked=blocked)
    def find_safest_route(self, origin_id, destination_id):
        for nid in (origin_id, destination_id):
            if nid not in self.graph:
                return None
        try:
            path = nx.dijkstra_path(self.graph, origin_id, destination_id, weight="weight")
            cost = nx.dijkstra_path_length(self.graph, origin_id, destination_id, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
        wps = []
        dist = 0.0
        risk = 0.0
        for i, nid in enumerate(path):
            lat, lon = self._coords[nid]
            nd = self.graph.nodes[nid]
            r = self.flood_model.get_point_risk(lat, lon)
            risk = max(risk, r)
            wps.append({
                "node_id": nid,
                "lat": lat,
                "lon": lon,
                "elevation_m": nd.get("elevation", 0.0),
                "label": nd.get("label", ""),
                "flood_risk": r,
            })
            if i > 0:
                pl, po = self._coords[path[i - 1]]
                dist += self._haversine(pl, po, lat, lon)
        return {
            "origin": origin_id,
            "destination": destination_id,
            "path": path,
            "waypoints": wps,
            "total_distance_m": round(dist, 1),
            "total_weight": round(cost, 2),
            "max_flood_risk": round(risk, 3),
            "hop_count": len(path) - 1,
        }
    def block_road(self, from_id, to_id, bidirectional=True):
        pairs = [(from_id, to_id)] + ([(to_id, from_id)] if bidirectional else [])
        for u, v in pairs:
            if self.graph.has_edge(u, v):
                self.graph[u][v]["weight"] = BLOCKED_WEIGHT
                self.graph[u][v]["blocked"] = True
    def unblock_road(self, from_id, to_id, bidirectional=True):
        pairs = [(from_id, to_id)] + ([(to_id, from_id)] if bidirectional else [])
        for u, v in pairs:
            if self.graph.has_edge(u, v):
                self.graph[u][v]["weight"] = self._edge_weight(u, v)
                self.graph[u][v]["blocked"] = False
    def refresh_edge_weights(self, node_id):
        for u, v in list(self.graph.out_edges(node_id)) + list(self.graph.in_edges(node_id)):
            if not self.graph[u][v].get("blocked", False):
                self.graph[u][v]["weight"] = self._edge_weight(u, v)
    def graph_info(self):
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "nodes": list(self.graph.nodes),
            "is_connected": nx.is_weakly_connected(self.graph) if self.graph.number_of_nodes() > 0 else False,
        }
    def _edge_weight(self, from_id, to_id):
        ca = self._coords[from_id]
        cb = self._coords[to_id]
        d = haversine(*ca, *cb)
        risk = self.flood_model.get_edge_risk(ca, cb, node_a_id=from_id, node_b_id=to_id)
        return round(d * (1.0 + SAFETY_MULTIPLIER * risk), 2)
