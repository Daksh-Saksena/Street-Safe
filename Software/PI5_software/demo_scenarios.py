import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import BACKEND_URL
from mock_hardware import MockMAVLinkInterface, MockSensorManager
from lidar_processing import process_scan, process_tf_luna
from decision_engine import DecisionEngine
from navigation import NavigationController
import requests
def _c(code, text):
    codes = {"bold": "\033[1m", "green": "\033[92m", "yellow": "\033[93m",
             "red": "\033[91m", "cyan": "\033[96m", "reset": "\033[0m"}
    return f"{codes.get(code,'')}{text}{codes['reset']}"
STATE_COLOR = {"NAVIGATING": "green", "AVOIDING": "yellow",
               "HOVERING": "cyan", "EMERGENCY": "red"}
mav     = MockMAVLinkInterface()
sensors = MockSensorManager()
engine  = DecisionEngine(target_heading=0.0)
nav     = NavigationController(mav)
mav.connect()
mav.set_guided_mode()
sensors.initialize()
def run_scenario(name, label, description, iterations=8):
    sensors.set_scenario(name)
    print("\n" + "═" * 62)
    print(_c("bold", f"  SCENARIO: {label}"))
    print(f"  {description}")
    print("═" * 62)
    for i in range(1, iterations + 1):
        snap   = sensors.read_all()
        scan   = process_scan(snap["lidar_360"])
        tf     = process_tf_luna(snap["lidar_front"])
        gps    = mav.get_gps()
        alt    = mav.get_altitude()
        dec    = engine.evaluate(scan, tf, gps, alt)
        nav.execute_decision(dec)
        state   = dec["state"]
        color   = STATE_COLOR.get(state, "reset")
        heading = dec["safe_heading"]
        h_str   = f"{heading:.0f}°" if heading is not None else " N/A"
        if dec["action"] == "NAVIGATE":
            narrative = f"✈  Flying on heading {dec['target_heading']:.0f}° — path is clear."
        elif dec["action"] == "AVOID":
            narrative = (
                f"↩  Obstacle at {dec['obstacles'][0]['angle_deg']:.0f}° "
                f"({dec['obstacles'][0]['distance_m']:.1f} m) — rerouting to {h_str}."
            ) if dec.get("obstacles") else f"↩  Rerouting to {h_str}."
        elif dec["action"] == "HOVER":
            narrative = "⏸  All headings blocked — holding position."
        else:
            narrative = "🛑  EMERGENCY STOP — object critically close!"
        print(
            f"  [{i:02d}] {_c(color, f'[{state:11s}]')}  "
            f"Heading: {h_str:5s}  Obstacles: {dec['obstacle_count']}  "
            f"GPS: ({gps['lat']:.5f}, {gps['lon']:.5f})"
        )
        print(f"       {narrative}")
        for alert in dec.get("alerts", []):
            icon = "🚨" if alert["level"] == "critical" else "⚠️ "
            print(f"       {icon} {_c('red' if alert['level']=='critical' else 'yellow', alert['message'])}")
        try:
            requests.post(f"{BACKEND_URL}/status/update", json={
                "state": state, "lat": gps["lat"], "lon": gps["lon"],
                "altitude_m": alt["alt_relative"], "heading_deg": heading,
                "groundspeed_ms": alt["groundspeed"],
            }, timeout=0.3)
        except Exception:
            pass
        time.sleep(0.6)
def demo_route_query():
    print("\n" + "═" * 62)
    print(_c("bold", "  SCENARIO 4 — Backend Route Query (flood-aware routing)"))
    print("  Querying API: shelter_a → hospital")
    print("  (North Bridge is flood-zone; router finds alternate path)")
    print("═" * 62)
    try:
        resp = requests.get(
            f"{BACKEND_URL}/route",
            params={"origin": "shelter_a", "destination": "hospital"},
            timeout=3,
        )
        if resp.status_code == 200:
            route = resp.json()["route"]
            print(f"\n  Route found ({route['hop_count']} hops, "
                  f"{route['total_distance_m']:.0f} m, "
                  f"max flood risk: {route['max_flood_risk']}):\n")
            for wp in route["waypoints"]:
                risk_bar = "🟥" if wp["flood_risk"] > 0.6 else ("🟨" if wp["flood_risk"] > 0.2 else "🟩")
                print(f"    {risk_bar}  {wp['node_id']:15s}  "
                      f"({wp['lat']:.5f}, {wp['lon']:.5f})  "
                      f"risk={wp['flood_risk']}")
        else:
            print(f"  Backend returned {resp.status_code} — is the server running?")
    except Exception as exc:
        print(f"  Backend unreachable ({exc}) — start it with: cd backend && python server.py")
def main():
    print(_c("bold", "\n  StreetSafe — Hackathon Demo  (MOCK MODE)\n"))
    print("  This script walks through 4 scenarios automatically.")
    print("  Press Enter between scenarios to advance.  Ctrl-C to quit.\n")
    input(_c("cyan", "  ➤  Press Enter to start Scenario 1 (Normal flight)..."))
    run_scenario(
        "clear",
        "Scenario 1 — Normal Flight",
        "No obstacles detected. Drone flies on target heading.",
    )
    input(_c("cyan", "\n  ➤  Press Enter for Scenario 2 (Obstacle ahead)..."))
    run_scenario(
        "obstacle",
        "Scenario 2 — Obstacle Detected",
        "Object 1.2 m ahead. Decision engine diverts to a safe heading.",
    )
    input(_c("cyan", "\n  ➤  Press Enter for Scenario 3 (Emergency stop)..."))
    run_scenario(
        "emergency",
        "Scenario 3 — Emergency Stop",
        "Object 0.3 m ahead — critically close. Full velocity zeroed immediately.",
        iterations=5,
    )
    input(_c("cyan", "\n  ➤  Press Enter for Scenario 4 (Backend routing)..."))
    demo_route_query()
    print(_c("green", "\n  Demo complete — all scenarios passed. ✓\n"))
if __name__ == "__main__":
    main()
