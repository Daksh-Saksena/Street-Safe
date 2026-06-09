import argparse
import logging
import os
import signal
import sys
import time
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import (
    MOCK_MODE,
    MAVLINK_CONNECTION,
    MAVLINK_BAUD,
    LIDAR_D500_PORT,
    TF_LUNA_PORT,
    LOOP_HZ,
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
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("/tmp/streetsafe.log")],
)
logger = logging.getLogger("main")
_running = True
def _handle_signal(sig, _frame):
    global _running
    logger.info("Shutdown signal received — stopping loop")
    _running = False
_COLORS = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}
def _c(color, text):
    return f"{_COLORS.get(color, '')}{text}{_COLORS['reset']}"
STATE_COLORS = {
    "NAVIGATING": "green",
    "AVOIDING":   "yellow",
    "HOVERING":   "cyan",
    "EMERGENCY":  "red",
}
def _print_status(decision, gps, alt):
    state = decision["state"]
    color = STATE_COLORS.get(state, "reset")
    hdg = decision["safe_heading"]
    hdg_str = f"{hdg:.0f}°" if hdg is not None else "N/A"
    lat = gps["lat"] if gps else "?"
    lon = gps["lon"] if gps else "?"
    a = alt["alt_relative"] if alt else "?"
    print(
        f"  {_c(color, f'[{state:11s}]')}  "
        f"Heading: {_c('bold', hdg_str):6s}  "
        f"Obstacles: {_c('red' if decision['obstacle_count'] else 'green', str(decision['obstacle_count']))}  "
        f"Terrain: {decision['terrain_class']:10s}  "
        f"GPS: ({lat}, {lon})  Alt: {a} m"
    )
    for alert in decision.get("alerts", []):
        lv = alert["level"].upper()
        icon = "🚨" if lv == "CRITICAL" else "⚠️ " if lv == "WARNING" else "ℹ️ "
        print(f"       {icon}  {_c('red' if lv == 'CRITICAL' else 'yellow', alert['message'])}")
def _announce_action(action, safe_heading, target_heading):
    if action == "NAVIGATE":
        print(f"  ✈  Flying toward heading {target_heading:.0f}° — path is clear.")
    elif action == "AVOID":
        print(f"  ↩  Obstacle detected! Rerouting: {target_heading:.0f}° → {safe_heading:.0f}°")
    elif action == "HOVER":
        print(f"  ⏸  All directions blocked — holding position.")
    elif action == "STOP":
        print(f"  🛑  EMERGENCY STOP — object too close!")
_t_scene = 0.0
_t_speed = 0.0
_t_loc = 0.0
def _push_to_backend(decision, scan, gps, alt):
    dm = {str(k): v for k, v in scan.get("distance_map", {}).items()}
    payload = {
        "state":          decision["state"],
        "lat":            gps["lat"] if gps else None,
        "lon":            gps["lon"] if gps else None,
        "altitude_m":     alt["alt_relative"] if alt else None,
        "heading_deg":    decision.get("safe_heading"),
        "groundspeed_ms": alt["groundspeed"] if alt else None,
        "action":         decision.get("action"),
        "alerts":         decision.get("alerts", []),
        "obstacles":      decision.get("obstacles", []),
        "terrain_class":  scan.get("terrain_class", "unknown"),
        "distance_map":   dm,
    }
    try:
        requests.post(f"{BACKEND_URL}/status/update", json=payload, timeout=0.5)
    except Exception:
        pass
def _poll_scenario(sensors):
    global _t_scene
    if not MOCK_MODE:
        return
    now = time.time()
    if now - _t_scene < 1.0:
        return
    _t_scene = now
    try:
        resp = requests.get(f"{BACKEND_URL}/scenario", timeout=0.3)
        if resp.status_code == 200:
            sensors.set_scenario(resp.json().get("scenario", "clear"))
    except Exception:
        pass
def _poll_speed(nav):
    global _t_speed
    if not MOCK_MODE:
        return
    now = time.time()
    if now - _t_speed < 1.0:
        return
    _t_speed = now
    try:
        resp = requests.get(f"{BACKEND_URL}/speed", timeout=0.3)
        if resp.status_code == 200:
            spd = float(resp.json().get("speed", 2.0))
            if abs(nav.cruise_speed - spd) > 0.05:
                nav.cruise_speed = spd
                if _mock_hw:
                    _mock_hw.set_speed(spd)
    except Exception:
        pass
def _poll_location():
    global _t_loc
    if not MOCK_MODE:
        return
    now = time.time()
    if now - _t_loc < 1.0:
        return
    _t_loc = now
    try:
        resp = requests.get(f"{BACKEND_URL}/location", timeout=0.3)
        if resp.status_code == 200:
            loc = resp.json().get("location")
            if loc and _mock_hw:
                _mock_hw.set_position(loc["lat"], loc["lon"])
    except Exception:
        pass
def main():
    global _running
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=["clear", "obstacle", "emergency"],
        default="clear",
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
    sensors = SensorManager() if MOCK_MODE else SensorManager(d500_port=LIDAR_D500_PORT, tf_luna_port=TF_LUNA_PORT)
    logger.info(f"Sensor status: {sensors.initialize()}")
    if MOCK_MODE:
        sensors.set_scenario(args.scenario)
    engine = DecisionEngine(target_heading=TARGET_HEADING)
    nav = NavigationController(mav)
    interval = 1.0 / LOOP_HZ
    iteration = 0
    print(f"  Control loop: {LOOP_HZ} Hz   Target heading: {TARGET_HEADING}°\n")
    while _running:
        t0 = time.time()
        iteration += 1
        try:
            mav.update_heartbeat()
            if not mav.is_connected():
                logger.error("Lost MAVLink connection — retrying in 1 s")
                time.sleep(1.0)
                continue
            snap = sensors.read_all()
            lidar = snap.get("lidar_360")
            tf_raw = snap.get("lidar_front")
            scan = (
                process_scan(lidar)
                if lidar
                else {"obstacles": [], "distance_map": {}, "terrain_class": "unknown"}
            )
            tf = process_tf_luna(tf_raw)
            gps = mav.get_gps()
            alt = mav.get_altitude()
            decision = engine.evaluate(
                processed_scan=scan,
                tf_luna_data=tf,
                gps_data=gps,
                altitude_data=alt,
            )
            print(f"\n── Iteration {iteration:04d} ──────────────────────────────────────")
            _print_status(decision, gps, alt)
            _announce_action(decision["action"], decision["safe_heading"], decision["target_heading"])
            nav.execute_decision(decision)
            _poll_scenario(sensors)
            _poll_speed(nav)
            _poll_location()
            _push_to_backend(decision, scan, gps, alt)
        except Exception:
            logger.exception("Unhandled error in control loop — continuing")
        elapsed = time.time() - t0
        if interval - elapsed > 0:
            time.sleep(interval - elapsed)
    print("\n" + _c("bold", "Shutting down StreetSafe..."))
    nav._hover()
    sensors.shutdown()
    mav.disconnect()
    print(_c("green", "Shutdown complete.\n"))
if __name__ == "__main__":
    main()
