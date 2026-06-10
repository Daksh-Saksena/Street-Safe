import logging
import time
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from flood_model import FloodModel
from routing_engine import RoutingEngine
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def _build_demo_network(engine):
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
        ("shelter_a",    "checkpoint_1", True, False),
        ("checkpoint_1", "hospital",     True, False),
        ("checkpoint_1", "supply_depot", True, False),
        ("shelter_a",    "shelter_b",    True, False),
        ("shelter_b",    "checkpoint_2", True, False),
        ("checkpoint_2", "bridge_north", True, False),
        ("bridge_north", "hospital",     True, False),
        ("rescue_base",  "checkpoint_2", True, False),
        ("rescue_base",  "shelter_b",    True, False),
        ("supply_depot", "shelter_a",    True, False),
    ]
    for from_id, to_id, bidir, blocked in roads:
        engine.add_road(from_id, to_id, bidir, blocked)
    engine.flood_model.register_flood_zone(lat=28.6198, lon=77.2102, radius_m=150, risk=0.85)
    engine.flood_model.register_flood_zone(lat=28.6172, lon=77.2138, radius_m=80, risk=0.60)
flood_model = FloodModel()
routing_engine = RoutingEngine(flood_model=flood_model)
_status = {
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
_scan = {"distance_map": {}, "obstacles": [], "terrain_class": "unknown"}
_dec = {"state": "NAVIGATING", "action": "NAVIGATE", "safe_heading": 0.0, "obstacle_count": 0, "alerts": []}
_scenario = "clear"
_speed = 2.0
_pinned = None
_obs = []
_obs_id = 0
@asynccontextmanager
async def lifespan(app: FastAPI):
    _build_demo_network(routing_engine)
    logger.info("StreetSafe backend ready")
    yield
    logger.info("StreetSafe backend shutting down")
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
class FloodZoneRequest(BaseModel):
    lat: float
    lon: float
    radius_m: float = Field(gt=0)
    risk: float = Field(default=0.8, ge=0.0, le=1.0)
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
    lat: float
    lon: float
@app.get("/")
def root():
    return {"service": "StreetSafe", "version": "1.0.0", "status": "running"}
@app.get("/route")
def get_route(origin: str = Query(...), destination: str = Query(...)):
    result = routing_engine.find_safest_route(origin, destination)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No passable route from '{origin}' to '{destination}'.")
    return {"success": True, "route": result}
@app.get("/status")
def get_status():
    return {
        "drone": _status,
        "network": routing_engine.graph_info(),
        "flood_zones": flood_model.summary(),
        "timestamp": time.time(),
    }
@app.post("/status/update")
def update_drone_status(update: DroneStatusUpdate):
    global _scan, _dec
    fields = update.model_dump(exclude_none=True)
    scan_d = {}
    dec_d = {}
    for key in ("obstacles", "terrain_class", "distance_map"):
        if key in fields:
            scan_d[key] = fields.pop(key)
    for key in ("action", "alerts", "state", "heading_deg"):
        if key in fields:
            dec_d[key] = fields.get(key)
    _status.update(fields)
    _status["last_update"] = time.time()
    if scan_d:
        _scan.update(scan_d)
    if dec_d:
        _dec.update(dec_d)
    return {"success": True, "drone": _status}
@app.get("/scan")
def get_scan():
    import math
    RANGE = 8.0
    dm = dict(_scan.get("distance_map", {}))
    sob = list(_scan.get("obstacles", []))
    dlat = _status.get("lat")
    dlon = _status.get("lon")
    if dlat is not None and dlon is not None:
        for o in _obs:
            olat, olon = o["lat"], o["lon"]
            R = 6_371_000
            f1, f2 = math.radians(dlat), math.radians(olat)
            df = math.radians(olat - dlat)
            dl = math.radians(olon - dlon)
            a = math.sin(df/2)**2 + math.cos(f1)*math.cos(f2)*math.sin(dl/2)**2
            dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            if dist > RANGE:
                continue
            y = math.sin(dl) * math.cos(f2)
            x = math.cos(f1)*math.sin(f2) - math.sin(f1)*math.cos(f2)*math.cos(dl)
            ang = (math.degrees(math.atan2(y, x)) + 360) % 360
            key = str(round(ang / 5.0) * 5.0)
            cur = dm.get(key)
            if cur is None or dist < cur:
                dm[key] = dist
            sob.append({
                "angle_deg": round(ang, 1),
                "distance_m": round(dist, 2),
                "severity": "critical" if dist < 0.5 else "warning" if dist < 1.0 else "caution",
                "custom": True,
            })
    out = dict(_scan)
    out["distance_map"] = dm
    out["obstacles"] = sob
    return {"scan": out, "decision": _dec, "scenario": _scenario, "speed": _speed, "timestamp": time.time()}
@app.post("/speed")
def set_speed(value: float = Query(..., ge=0.0, le=15.0)):
    global _speed
    _speed = value
    logger.info(f"Speed → {value} m/s")
    return {"success": True, "speed": _speed}
@app.get("/speed")
def get_speed():
    return {"speed": _speed}
@app.post("/location")
def pin_location(
    lat: float = Query(...),
    lon: float = Query(...),
):
    global _pinned
    _pinned = {"lat": lat, "lon": lon}
    _status["lat"] = lat
    _status["lon"] = lon
    logger.info(f"Location pinned → ({lat:.6f}, {lon:.6f})")
    return {"success": True, "location": _pinned}
@app.get("/location")
def get_location():
    return {"location": _pinned}
@app.post("/obstacle")
def add_obstacle(req: ObstacleRequest):
    global _obs_id
    _obs_id += 1
    o = {"id": _obs_id, "lat": req.lat, "lon": req.lon}
    _obs.append(o)
    return {"success": True, "obstacle": o}
@app.delete("/obstacle/{obs_id}")
def remove_obstacle(obs_id: int):
    global _obs
    before = len(_obs)
    _obs = [o for o in _obs if o["id"] != obs_id]
    return {"success": True, "removed": before - len(_obs)}
@app.post("/obstacles/clear")
def clear_obstacles():
    global _obs
    n = len(_obs)
    _obs = []
    return {"success": True, "cleared": n}
@app.get("/obstacles")
def list_obstacles():
    return {"obstacles": _obs}
@app.post("/scenario")
def set_scenario(name: str = Query(...)):
    global _scenario
    if name not in {"clear", "obstacle", "emergency"}:
        raise HTTPException(status_code=400, detail=f"Invalid scenario: {name}")
    _scenario = name
    logger.info(f"Scenario → {name}")
    return {"success": True, "scenario": _scenario}
@app.get("/scenario")
def get_scenario():
    return {"scenario": _scenario}
@app.post("/flood-zone")
def add_flood_zone(req: FloodZoneRequest):
    flood_model.register_flood_zone(req.lat, req.lon, req.radius_m, req.risk)
    for node_id in routing_engine.graph.nodes:
        routing_engine.refresh_edge_weights(node_id)
    return {"success": True, "flood_zones": flood_model.summary()}
@app.post("/block-road")
def block_road(req: BlockRoadRequest):
    routing_engine.block_road(req.from_id, req.to_id, req.bidirectional)
    return {"success": True, "blocked": req.model_dump()}
@app.post("/unblock-road")
def unblock_road(req: BlockRoadRequest):
    routing_engine.unblock_road(req.from_id, req.to_id, req.bidirectional)
    return {"success": True, "unblocked": req.model_dump()}
@app.get("/graph")
def get_graph():
    nodes = [
        {
            "id": nid,
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "elevation_m": data.get("elevation", 0),
            "label": data.get("label", ""),
            "flood_risk": flood_model.get_point_risk(data.get("lat", 0.0), data.get("lon", 0.0)),
        }
        for nid, data in routing_engine.graph.nodes(data=True)
    ]
    edges = [
        {"from": u, "to": v, "weight": data.get("weight"), "blocked": data.get("blocked", False)}
        for u, v, data in routing_engine.graph.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
