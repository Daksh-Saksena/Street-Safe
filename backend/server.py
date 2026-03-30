import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from flood_model import FloodModel, RISK_HIGH
from routing_engine import RoutingEngine
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def _build_demo_network(engine: RoutingEngine) -> None:
    nodes = [
        ("shelter_a",    28.6140, 77.2091, 12.0, "Main Shelter A"),
        ("shelter_b",    28.6165, 77.2120, 10.0, "Shelter B — School"),
        ("hospital",     28.6180, 77.2085,  8.0, "District Hospital"),
        ("supply_depot", 28.6110, 77.2060, 15.0, "Supply Depot"),
        ("bridge_north", 28.6200, 77.2100,  5.0, "North Bridge"),
        ("rescue_base",  28.6130, 77.2150,  9.0, "Rescue Base Camp"),
        ("checkpoint_1", 28.6150, 77.2075, 11.0, "Checkpoint 1"),
        ("checkpoint_2", 28.6170, 77.2140,  7.0, "Checkpoint 2"),
    ]
    for nid, lat, lon, elev, label in nodes:
        engine.add_node(nid, lat, lon, elev, label)
    roads = [
        ("shelter_a",    "checkpoint_1", True,  False),
        ("checkpoint_1", "hospital",     True,  False),
        ("checkpoint_1", "supply_depot", True,  False),
        ("shelter_a",    "shelter_b",    True,  False),
        ("shelter_b",    "checkpoint_2", True,  False),
        ("checkpoint_2", "bridge_north", True,  False),
        ("bridge_north", "hospital",     True,  False),
        ("rescue_base",  "checkpoint_2", True,  False),
        ("rescue_base",  "shelter_b",    True,  False),
        ("supply_depot", "shelter_a",    True,  False),
    ]
    for from_id, to_id, bidir, blocked in roads:
        engine.add_road(from_id, to_id, bidir, blocked)
    engine.flood_model.register_flood_zone(
        lat=28.6198, lon=77.2102, radius_m=150, risk=0.85
    )  
    engine.flood_model.register_flood_zone(
        lat=28.6172, lon=77.2138, radius_m=80, risk=0.60
    )  
    logger.info("Demo network loaded (8 nodes, 10 road segments, 2 flood zones)")
flood_model = FloodModel()
routing_engine = RoutingEngine(flood_model=flood_model)
_drone_status: Dict[str, Any] = {
    "connected": True,
    "state": "NAVIGATING",
    "lat": 28.6140,
    "lon": 77.2091,
    "altitude_m": 10.0,
    "heading_deg": 0.0,
    "groundspeed_ms": 0.0,
    "battery_pct": 100,
    "sensor_status": {"d500": True, "tf_luna": True},
    "last_update": time.time(),
}
_latest_scan: Dict[str, Any] = {"distance_map": {}, "obstacles": [], "terrain_class": "unknown"}
_latest_decision: Dict[str, Any] = {"state": "NAVIGATING", "action": "NAVIGATE",
                                    "safe_heading": 0.0, "obstacle_count": 0, "alerts": []}
_active_scenario: str = "clear"
_drone_speed: float = 2.0
_pinned_location: Optional[Dict[str, float]] = None
_custom_obstacles: list = []
_obstacle_id_counter: int = 0
@asynccontextmanager
async def lifespan(app: FastAPI):
    _build_demo_network(routing_engine)
    logger.info("StreetSafe backend ready")
    yield
    logger.info("StreetSafe backend shutting down")
app = FastAPI(
    title="StreetSafe API",
    description="Disaster-response drone routing and status API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_methods=["*"],
    allow_headers=["*"],
)
class FloodZoneRequest(BaseModel):
    lat: float
    lon: float
    radius_m: float = Field(gt=0, description="Flood zone radius in metres")
    risk: float = Field(default=0.8, ge=0.0, le=1.0, description="Risk score 0–1")
class BlockRoadRequest(BaseModel):
    from_id: str
    to_id: str
    bidirectional: bool = True
class DroneStatusUpdate(BaseModel):
    state: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    altitude_m: Optional[float] = None
    heading_deg: Optional[float] = None
    groundspeed_ms: Optional[float] = None
    battery_pct: Optional[int] = Field(default=None, ge=0, le=100)
    obstacles: Optional[list] = None
    terrain_class: Optional[str] = None
    distance_map: Optional[dict] = None
    action: Optional[str] = None
    alerts: Optional[list] = None
class ObstacleRequest(BaseModel):
    lat: float = Field(description="Latitude of obstacle")
    lon: float = Field(description="Longitude of obstacle")
@app.get("/", tags=["Health"])
def root() -> Dict:
    return {"service": "StreetSafe", "version": "1.0.0", "status": "running"}
@app.get("/route", tags=["Routing"])
def get_route(
    origin: str = Query(..., description="Origin node ID"),
    destination: str = Query(..., description="Destination node ID"),
) -> Dict:
    result = routing_engine.find_safest_route(origin, destination)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No passable route from '{origin}' to '{destination}'. "
                   "Check that both node IDs exist and a clear path connects them.",
        )
    return {"success": True, "route": result}
@app.get("/status", tags=["Telemetry"])
def get_status() -> Dict:
    return {
        "drone": _drone_status,
        "network": routing_engine.graph_info(),
        "flood_zones": flood_model.summary(),
        "timestamp": time.time(),
    }
@app.post("/status/update", tags=["Telemetry"])
def update_drone_status(update: DroneStatusUpdate) -> Dict:
    global _latest_scan, _latest_decision
    fields = update.model_dump(exclude_none=True)
    scan_update = {}
    decision_update = {}
    for key in ("obstacles", "terrain_class", "distance_map"):
        if key in fields:
            scan_update[key] = fields.pop(key)
    for key in ("action", "alerts", "state", "heading_deg"):
        if key in fields:
            decision_update[key] = fields.get(key)  
    _drone_status.update(fields)
    _drone_status["last_update"] = time.time()
    if scan_update:
        _latest_scan.update(scan_update)
    if decision_update:
        _latest_decision.update(decision_update)
    return {"success": True, "drone": _drone_status}
@app.get("/scan", tags=["Telemetry"])
def get_scan() -> Dict:
    merged_dm = dict(_latest_scan.get("distance_map", {}))
    merged_obs = list(_latest_scan.get("obstacles", []))
    SENSOR_RANGE_M = 8.0
    drone_lat = _drone_status.get("lat")
    drone_lon = _drone_status.get("lon")
    if drone_lat is not None and drone_lon is not None:
        import math
        for cobs in _custom_obstacles:
            olat, olon = cobs["lat"], cobs["lon"]
            R = 6_371_000
            f1, f2 = math.radians(drone_lat), math.radians(olat)
            df = math.radians(olat - drone_lat)
            dl = math.radians(olon - drone_lon)
            a = math.sin(df/2)**2 + math.cos(f1)*math.cos(f2)*math.sin(dl/2)**2
            dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            if dist > SENSOR_RANGE_M:
                continue  
            y = math.sin(dl) * math.cos(f2)
            x = math.cos(f1)*math.sin(f2) - math.sin(f1)*math.cos(f2)*math.cos(dl)
            ang = (math.degrees(math.atan2(y, x)) + 360) % 360
            bucket_key = str(round(ang / 5.0) * 5.0)
            existing = merged_dm.get(bucket_key)
            if existing is None or dist < existing:
                merged_dm[bucket_key] = dist
            merged_obs.append({
                "angle_deg":  round(ang, 1),
                "distance_m": round(dist, 2),
                "severity":   "critical" if dist < 0.5 else "warning" if dist < 1.0 else "caution",
                "custom":     True,
            })
    scan_out = dict(_latest_scan)
    scan_out["distance_map"] = merged_dm
    scan_out["obstacles"]    = merged_obs
    return {
        "scan":     scan_out,
        "decision": _latest_decision,
        "scenario": _active_scenario,
        "speed":    _drone_speed,
        "timestamp": time.time(),
    }
@app.post("/speed", tags=["Control"])
def set_speed(value: float = Query(..., ge=0.0, le=15.0, description="Cruise speed in m/s")) -> Dict:
    global _drone_speed
    _drone_speed = value
    logger.info(f"Drone speed → {value} m/s")
    return {"success": True, "speed": _drone_speed}
@app.get("/speed", tags=["Control"])
def get_speed() -> Dict:
    return {"speed": _drone_speed}
@app.post("/location", tags=["Control"])
def pin_location(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
) -> Dict:
    global _pinned_location
    _pinned_location = {"lat": lat, "lon": lon}
    _drone_status["lat"] = lat
    _drone_status["lon"] = lon
    logger.info(f"Location pinned → ({lat:.6f}, {lon:.6f})")
    return {"success": True, "location": _pinned_location}
@app.get("/location", tags=["Control"])
def get_location() -> Dict:
    return {"location": _pinned_location}
@app.post("/obstacle", tags=["Control"])
def add_obstacle(req: ObstacleRequest) -> Dict:
    global _obstacle_id_counter
    _obstacle_id_counter += 1
    obs = {"id": _obstacle_id_counter, "lat": req.lat, "lon": req.lon}
    _custom_obstacles.append(obs)
    logger.info(f"Obstacle added: {obs}")
    return {"success": True, "obstacle": obs}
@app.delete("/obstacle/{obs_id}", tags=["Control"])
def remove_obstacle(obs_id: int) -> Dict:
    global _custom_obstacles
    before = len(_custom_obstacles)
    _custom_obstacles = [o for o in _custom_obstacles if o["id"] != obs_id]
    removed = before - len(_custom_obstacles)
    return {"success": True, "removed": removed}
@app.post("/obstacles/clear", tags=["Control"])
def clear_obstacles() -> Dict:
    global _custom_obstacles
    count = len(_custom_obstacles)
    _custom_obstacles = []
    logger.info(f"Cleared {count} custom obstacles")
    return {"success": True, "cleared": count}
@app.get("/obstacles", tags=["Control"])
def list_obstacles() -> Dict:
    return {"obstacles": _custom_obstacles}
@app.post("/scenario", tags=["Demo"])
def set_scenario(name: str = Query(..., description="Scenario: clear | obstacle | emergency")) -> Dict:
    global _active_scenario
    valid = {"clear", "obstacle", "emergency"}
    if name not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid scenario. Choose from: {valid}")
    _active_scenario = name
    logger.info(f"Scenario changed → {name}")
    return {"success": True, "scenario": _active_scenario}
@app.get("/scenario", tags=["Demo"])
def get_scenario() -> Dict:
    return {"scenario": _active_scenario}
@app.post("/flood-zone", tags=["Environment"])
def add_flood_zone(req: FloodZoneRequest) -> Dict:
    flood_model.register_flood_zone(req.lat, req.lon, req.radius_m, req.risk)
    for node_id in routing_engine.graph.nodes:
        routing_engine.refresh_edge_weights(node_id)
    return {"success": True, "flood_zones": flood_model.summary()}
@app.post("/block-road", tags=["Environment"])
def block_road(req: BlockRoadRequest) -> Dict:
    routing_engine.block_road(req.from_id, req.to_id, req.bidirectional)
    return {"success": True, "blocked": req.model_dump()}
@app.post("/unblock-road", tags=["Environment"])
def unblock_road(req: BlockRoadRequest) -> Dict:
    routing_engine.unblock_road(req.from_id, req.to_id, req.bidirectional)
    return {"success": True, "unblocked": req.model_dump()}
@app.get("/graph", tags=["Routing"])
def get_graph() -> Dict:
    nodes = [
        {
            "id": nid,
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "elevation_m": data.get("elevation", 0),
            "label": data.get("label", ""),
            "flood_risk": flood_model.get_point_risk(
                data.get("lat", 0.0), data.get("lon", 0.0)
            ),
        }
        for nid, data in routing_engine.graph.nodes(data=True)
    ]
    edges = [
        {
            "from": u,
            "to": v,
            "weight": data.get("weight"),
            "blocked": data.get("blocked", False),
        }
        for u, v, data in routing_engine.graph.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
