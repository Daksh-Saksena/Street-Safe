import argparse
import logging
import signal
import sys
import time
from typing import Optional
import requests
sys.path.insert(0, "../shared")
from config import (
    MOCK_MODE,
    MAVLINK_CONNECTION,
    MAVLINK_BAUD,
    LIDAR_D500_PORT,
    TF_LUNA_PORT,
    LOOP_HZ,
    HOME_LAT,
    HOME_LON,
    TARGET_HEADING,
    DEFAULT_ALTITUDE_M,
    BACKEND_URL,
)
if MOCK_MODE:
    from mock_hardware import MockMAVLinkInterface as MAVLinkInterface
    from mock_hardware import MockSensorManager as SensorManager
    import mock_hardware as _mock_hw   
else:
    from mavlink_interface import MAVLinkInterface
    from sensor_manager import SensorManager
    _mock_hw = None  
from lidar_processing import process_scan, process_tf_luna
from decision_engine import DecisionEngine
from navigation import NavigationController
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/streetsafe.log"),
    ],
)
logger = logging.getLogger("main")
_running: bool = True
def _handle_signal(sig: int, _frame: object) -> None:
    global _running
    logger.info(f"Shutdown signal received — stopping loop")
    _running = False
_COLORS = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}
def _c(color: str, text: str) -> str:
    return f"{_COLORS.get(color, '')}{text}{_COLORS['reset']}"
STATE_COLORS = {
    "NAVIGATING": "green",
    "AVOIDING":   "yellow",
    "HOVERING":   "cyan",
    "EMERGENCY":  "red",
}
def _print_status(decision: dict, gps: Optional[dict], altitude: Optional[dict]) -> None:
    state = decision["state"]
    color = STATE_COLORS.get(state, "reset")
    heading = decision["safe_heading"]
    heading_str = f"{heading:.0f}°" if heading is not None else "N/A"
    obstacles = decision["obstacle_count"]
    terrain = decision["terrain_class"]
    lat = gps["lat"] if gps else "?"
    lon = gps["lon"] if gps else "?"
    alt = altitude["alt_relative"] if altitude else "?"
    print(
        f"  {_c(color, f'[{state:11s}]')}  "
        f"Heading: {_c('bold', heading_str):6s}  "
        f"Obstacles: {_c('red' if obstacles else 'green', str(obstacles))}  "
        f"Terrain: {terrain:10s}  "
        f"GPS: ({lat}, {lon})  Alt: {alt} m"
    )
    for alert in decision.get("alerts", []):
        level = alert["level"].upper()
        icon = "🚨" if level == "CRITICAL" else "⚠️ " if level == "WARNING" else "ℹ️ "
        print(f"       {icon}  {_c('red' if level == 'CRITICAL' else 'yellow', alert['message'])}")
def _announce_action(action: str, safe_heading: Optional[float], target_heading: float) -> None:
    if action == "NAVIGATE":
        print(f"  ✈  Flying toward heading {target_heading:.0f}° — path is clear.")
    elif action == "AVOID":
        print(f"  ↩  Obstacle detected! Rerouting: {target_heading:.0f}° → {safe_heading:.0f}°")
    elif action == "HOVER":
        print(f"  ⏸  All directions blocked — holding position.")
    elif action == "STOP":
        print(f"  🛑  EMERGENCY STOP — object too close!")
_last_scenario_poll: float = 0.0   
_last_speed_poll: float = 0.0
_last_location_poll: float = 0.0
def _push_to_backend(
    decision: dict,
    processed_scan: dict,
    gps: Optional[dict],
    altitude: Optional[dict],
) -> None:
    distance_map_serialized = {
        str(k): v for k, v in processed_scan.get("distance_map", {}).items()
    }
    payload = {
        "state":          decision["state"],
        "lat":            gps["lat"]  if gps  else None,
        "lon":            gps["lon"]  if gps  else None,
        "altitude_m":     altitude["alt_relative"] if altitude else None,
        "heading_deg":    decision.get("safe_heading"),
        "groundspeed_ms": altitude["groundspeed"] if altitude else None,
        "action":         decision.get("action"),
        "alerts":         decision.get("alerts", []),
        "obstacles":      decision.get("obstacles", []),
        "terrain_class":  processed_scan.get("terrain_class", "unknown"),
        "distance_map":   distance_map_serialized,
    }
    try:
        requests.post(f"{BACKEND_URL}/status/update", json=payload, timeout=0.5)
    except Exception:
        pass   
def _poll_scenario(sensors: object) -> None:
    global _last_scenario_poll
    if not MOCK_MODE:
        return
    now = time.time()
    if now - _last_scenario_poll < 1.0:
        return
    _last_scenario_poll = now
    try:
        resp = requests.get(f"{BACKEND_URL}/scenario", timeout=0.3)
        if resp.status_code == 200:
            name = resp.json().get("scenario", "clear")
            sensors.set_scenario(name)  
    except Exception:
        pass
def _poll_speed(nav: object) -> None:
    global _last_speed_poll
    if not MOCK_MODE:
        return
    now = time.time()
    if now - _last_speed_poll < 1.0:
        return
    _last_speed_poll = now
    try:
        resp = requests.get(f"{BACKEND_URL}/speed", timeout=0.3)
        if resp.status_code == 200:
            speed = float(resp.json().get("speed", 2.0))
            if abs(nav.cruise_speed - speed) > 0.05:
                nav.cruise_speed = speed
                if _mock_hw:
                    _mock_hw.set_speed(speed)
    except Exception:
        pass
def _poll_location() -> None:
    global _last_location_poll
    if not MOCK_MODE:
        return
    now = time.time()
    if now - _last_location_poll < 1.0:
        return
    _last_location_poll = now
    try:
        resp = requests.get(f"{BACKEND_URL}/location", timeout=0.3)
        if resp.status_code == 200:
            loc = resp.json().get("location")
            if loc and _mock_hw:
                _mock_hw.set_position(loc["lat"], loc["lon"])
    except Exception:
        pass
def main() -> None:
    global _running
    parser = argparse.ArgumentParser(description="StreetSafe drone control loop")
    parser.add_argument(
        "--scenario",
        choices=["clear", "obstacle", "emergency"],
        default="clear",
        help="Starting obstacle scenario (mock mode only)",
    )
    args = parser.parse_args()
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    mode_label = _c("yellow", "MOCK") if MOCK_MODE else _c("green", "HARDWARE")
    print(_c("bold", f"\n{'═'*60}"))
    print(_c("bold", f"  StreetSafe Drone System  [{mode_label}\033[1m]"))
    print(_c("bold", f"{'═'*60}\n"))
    mav = MAVLinkInterface() if MOCK_MODE else MAVLinkInterface(MAVLINK_CONNECTION, MAVLINK_BAUD)
    if not mav.connect():
        logger.critical("Could not connect to flight controller — aborting")
        sys.exit(1)
    mav.set_guided_mode()
    sensors = SensorManager() if MOCK_MODE else SensorManager(
        d500_port=LIDAR_D500_PORT, tf_luna_port=TF_LUNA_PORT
    )
    sensor_status = sensors.initialize()
    logger.info(f"Sensor status: {sensor_status}")
    if MOCK_MODE:
        sensors.set_scenario(args.scenario)
    engine = DecisionEngine(target_heading=TARGET_HEADING)
    nav = NavigationController(mav)
    loop_interval = 1.0 / LOOP_HZ
    iteration = 0
    print(f"  Control loop: {LOOP_HZ} Hz   Target heading: {TARGET_HEADING}°\n")
    while _running:
        loop_start = time.time()
        iteration += 1
        try:
            mav.update_heartbeat()
            if not mav.is_connected():
                logger.error("Lost MAVLink connection — retrying in 1 s")
                time.sleep(1.0)
                continue
            snap = sensors.read_all()
            raw_scan = snap.get("lidar_360")
            raw_tf   = snap.get("lidar_front")
            processed_scan = (
                process_scan(raw_scan)
                if raw_scan
                else {"obstacles": [], "distance_map": {}, "terrain_class": "unknown"}
            )
            tf_result = process_tf_luna(raw_tf)
            gps_data      = mav.get_gps()
            altitude_data = mav.get_altitude()
            decision = engine.evaluate(
                processed_scan=processed_scan,
                tf_luna_data=tf_result,
                gps_data=gps_data,
                altitude_data=altitude_data,
            )
            print(f"\n── Iteration {iteration:04d} ──────────────────────────────────────")
            _print_status(decision, gps_data, altitude_data)
            _announce_action(decision["action"], decision["safe_heading"], decision["target_heading"])
            nav.execute_decision(decision)
            _poll_scenario(sensors)
            _poll_speed(nav)
            _poll_location()
            _push_to_backend(decision, processed_scan, gps_data, altitude_data)
        except Exception:
            logger.exception("Unhandled error in control loop — continuing")
        elapsed = time.time() - loop_start
        sleep_time = loop_interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
    print("\n" + _c("bold", "Shutting down StreetSafe..."))
    nav._hover()
    sensors.shutdown()
    mav.disconnect()
    print(_c("green", "Shutdown complete.\n"))
if __name__ == "__main__":
    main()
