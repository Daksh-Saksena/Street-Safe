from car import Cars, get_vehicle_profile, create_vehicle
from cost import compute_edge_weight
from router import compute_route 
import networkx as nx
import random
import json 


# simulating car traffic with random start and end points, and random vehicle types. The results include the path taken and the total cost of the route.
available_types = ["car", "suv", "bike"]
def simulate_traffic(g, all_nodes, vehicles=100,):
    results = []
    for i in range(vehicles):
        # handling car creation
        vehicle_type = random.choice(available_types)
        car = create_vehicle(id = str(i),type = vehicle_type)

        # handling coordinates: picking random start, end, getting their coordinates
        u, v = random.sample(all_nodes, 2)
        start_coord = (g.nodes[u]['y'], g.nodes[u]['x'])
        end_coord = (g.nodes[v]['y'], g.nodes[v]['x'])

        # result of routing
        route_result = compute_route(g, start_coord, end_coord, car['profile'])
        if route_result["status"] == "success":
            path = route_result["path"]
            
            # Calculate total cost 
            total_cost = 0
            coord_path = []
            for j in range(len(path) - 1):
                u_node, v_node = path[j], path[j+1]
                edge_data = g[u_node][v_node][0] 
                total_cost += compute_edge_weight(edge_data, car['profile'])
                coord_path.append([g.nodes[u_node]['y'], g.nodes[u_node]['x']])
            
            # Add the very last node coordinate
            coord_path.append([g.nodes[path[-1]]['y'], g.nodes[path[-1]]['x']])

            results.append({
                 "vehicle_id": i,
                 "vehicle_type": vehicle_type,
                 "status": "success",
                 "start_node": u,
                 "end_node": v,
                 "path_coords": coord_path, 
                 "total_cost": total_cost
            })
        else:
            results.append({
                "vehicle_id": i,
                "vehicle_type": vehicle_type,
                "status": "stranded",
                "start_node": u,
                "start_coord": [start_coord[0], start_coord[1]],
                "total_cost": float('inf')
            })
            
    return results
    

        