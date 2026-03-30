import networkx as nx
from cost import compute_edge_weight
from car import get_vehicle_profile, create_vehicle, Cars
import random 
from osmnx import nearest_nodes
#computes route based on the graph, start and end nodes, and vehicle profile. It first computes edge weights using the cost function and then uses Dijkstra's algorithm to find the shortest path based on those weights.
def compute_route(g: nx.Graph, starting_coord: int, target_coord: int, vehicle_profile: Cars) -> list:
    starting_node = nearest_nodes(g, starting_coord[1], starting_coord[0])
    target_node = nearest_nodes(g, target_coord[1], target_coord[0])
    def weight_function(u, v, d):
        edge_data = d if isinstance(d, dict) else g[u][v][0]
        return compute_edge_weight(edge_data, vehicle_profile)
    try:
        path = nx.dijkstra_path(g, source=starting_node, target=target_node, weight=weight_function)
        return {
            'path': path,
            'vehicle_type'  : vehicle_profile.name,
            'status' : 'success'
        } 
    except nx.NetworkXNoPath:
        return {
            'path': [],
            'vehicle_type': vehicle_profile.name,
            'status': 'blocked'
        }




