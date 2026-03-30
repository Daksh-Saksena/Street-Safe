# vehicle stats 

from dataclasses import dataclass
@dataclass
class Cars:
    name: str
    base_speed_kmph: float
    road_multipliers: dict
    impassable_flood_depth_m: float
    flood_speed_loss_per_mm: float
    flood_penalty_lambda: float
    color: str


suv = Cars(
    name = "suv",
    base_speed_kmph = 50,
    road_multipliers = {"highway": 2.0, "primary": 1.0, "secondary": 0.85, "residential": 0.65 },
    impassable_flood_depth_m = 0.6,
    flood_speed_loss_per_mm = 0.1,
    flood_penalty_lambda = 50,
    color = "#1f77b4"
)

car = Cars(
    name = "car",
    base_speed_kmph = 55,
    road_multipliers = {"highway": 1.8, "primary": 0.9, "secondary": 0.75, "residential": 0.75 },
    impassable_flood_depth_m = 0.3,
    flood_speed_loss_per_mm = 0.2, 
    flood_penalty_lambda = 200,
    color = "#ff7f0e"
)

bike = Cars(
    name = "bike",
    base_speed_kmph = 40,
    road_multipliers = {"highway": 1.5, "primary": 1.0, "secondary": 0.9, "residential": 0.8 },
    impassable_flood_depth_m = 0.1,
    flood_speed_loss_per_mm = 0.5,
    flood_penalty_lambda = 500,
    color = "#2ca02c"
)   

# get vehicle profile by type
def get_vehicle_profile(vehicle_type):
    profiles = {
        "suv": suv,
        "car": car,
        "bike": bike
    }
    return profiles.get(vehicle_type.lower())

#creating vehicle object

def create_vehicle(id : str, type : str):
    vehicle_profile = get_vehicle_profile(type)
    if vehicle_profile is None:
        raise ValueError(f"Unknown vehicle type: {type}")
    return {
        "id": id,
        "type": type,
        "profile": vehicle_profile,
        "origin": None,
        "destination": None,
        "route": [],
        "stats": {}
    }