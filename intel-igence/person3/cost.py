# file to find cost of each route, for a specific car
# networkx sees which route has lowest cost for a particular car, and then decides which route it will use

from car import Cars 

# finds the speed that the car will travel at in a flood of given depth
def compute_speed_in_flood(base_speed_kmph, flood_depth_m, loss_rate_per_mm):
    flood_depth_mm = flood_depth_m * 1000
    speed_loss = loss_rate_per_mm * flood_depth_mm
    adjusted_speed_kmph = max(base_speed_kmph - speed_loss, 0)
    return max(0.1, adjusted_speed_kmph)  

#finds time taken to travel a given edge length at a given speed
def compute_travel_time(edge_length_m, speed_kmph):
    speed_mps = speed_kmph * 5/18
    travel_time_s = edge_length_m/speed_mps 
    return travel_time_s

# finds the area of flooding on a given edge, which is used to calculate the penalty for that edge
def compute_flooding_exposure(flood_depth_m, edge_length_m):
    exposure = flood_depth_m * edge_length_m
    return exposure
# computes the weight(cost) of an edge (road) for the given car, flood depth, road class, and edge length
def compute_edge_weight(edge_data : dict, vehicle_profile : Cars) -> float: 
    flood_depth = edge_data.get('flood_depth', 0.0)
    if flood_depth >= vehicle_profile.impassable_flood_depth_m:
        return float('inf') # The router will treat this road as a wall
    else:
        road_class = edge_data.get('road_class', 'residential')
        road_multiplier = vehicle_profile.road_multipliers.get(road_class, 1.0)
        edge_length_m = edge_data.get('length', 100.0)
        base_speed_kmph = vehicle_profile.base_speed_kmph * road_multiplier
        flood_speed_kmph = compute_speed_in_flood(base_speed_kmph, flood_depth, vehicle_profile.flood_speed_loss_per_mm)
        travel_time_s = compute_travel_time(edge_length_m, flood_speed_kmph)
        exposure = compute_flooding_exposure(flood_depth, edge_length_m)
        edge_weight = travel_time_s + (exposure * vehicle_profile.flood_penalty_lambda)
        return edge_weight




    
    


