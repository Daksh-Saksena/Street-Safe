# WHover need this js directly use results from compute_all_roads - arpu babez
#Daksh plz fill in the road and thr data in roads. If u want u can put name instead of id.

roads = [
    {
        "id": 101,
        "length": 120.5,
        "avg_elevation": 9.8,
        "min_elev": 4.2,
        "max_elev": 15
    },
    {
        "id": 102,
        "length": 80,
        "avg_elevation": 6.5,
        "min_elev": 3,
        "max_elev": 7
    },
    {
        "id": 103,
        "length": 200,
        "avg_elevation": 12,
        "min_elev": 10,
        "max_elev": 14
    }
]
rain_mm = int(input("Enter rain amount: "))

RAIN_WEIGHT = 0.55
ELEV_WEIGHT = 0.25
FLAT_WEIGHT = 0.20


def normalize_rain(mm_per_hr):
    MAX_RAIN = 50.0
    return max(0, min(1, mm_per_hr / MAX_RAIN))



def compute_road_risk(road, rain_mm):
    rain_norm = normalize_rain(rain_mm)
    slope = (road["max_elev"] - road["min_elev"]) / road["length"]
    slope = max(0, min(1, slope))
    flatness = 1 - slope
    norm_elev = (road["avg_elevation"] - road["min_elev"]) / (
        road["max_elev"] - road["min_elev"]
    )
    low_elev_factor = 1 - norm_elev
    risk = (
        rain_norm * RAIN_WEIGHT +
        low_elev_factor * ELEV_WEIGHT +
        flatness * FLAT_WEIGHT
    )
    risk = max(0, min(1, risk))
    if risk > 0.7:
        level = "very high"
    elif risk > 0.45:
        level = "high"
    elif risk > 0.2:
        level = "medium"
    else:
        level = "low"

    return risk, level

def compute_all_roads(roads, rain_mm):
    results = []
    for road in roads:
        risk, level = compute_road_risk(road, rain_mm)
        results.append({
            "road_id": road["id"],
            "risk": round(risk, 2),
            "level": level
        })
    return results

def get_safe_roads(results, threshold=0.5):
    return [r for r in results if r["risk"] <= threshold]


results = compute_all_roads(roads, rain_mm)
safe_roads = get_safe_roads(results, threshold=0.5)

for r in results:
    print(f"Road {r['road_id']} → Risk: {r['risk']:.2f}, Level: {r['level']}")

print("Safe roads:", safe_roads)

    #WHover need this js directly use results from compute_all_roads - arpu babez