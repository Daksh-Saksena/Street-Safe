import math
import time
import logging
from typing import Optional, Dict
from pymavlink import mavutil
logger = logging.getLogger(__name__)
class MAVLinkInterface:
    def __init__(self, connection_string: str, baud_rate: int = 115200) -> None:
        self.connection_string = connection_string
        self.baud_rate = baud_rate
        self.vehicle = None          
        self._last_heartbeat: float = 0.0
    def connect(self) -> bool:
        try:
            logger.info(f"Connecting to flight controller at {self.connection_string}")
            self.vehicle = mavutil.mavlink_connection(
                self.connection_string,
                baud=self.baud_rate,
            )
            self.vehicle.wait_heartbeat(timeout=10)
            self._last_heartbeat = time.time()
            logger.info(
                f"Connected — system_id={self.vehicle.target_system} "
                f"component_id={self.vehicle.target_component}"
            )
            return True
        except Exception as exc:
            logger.error(f"Failed to connect to flight controller: {exc}")
            return False
    def is_connected(self) -> bool:
        if self.vehicle is None:
            return False
        return (time.time() - self._last_heartbeat) < 5.0
    def update_heartbeat(self) -> None:
        if self.vehicle is None:
            return
        msg = self.vehicle.recv_match(blocking=False)
        if msg and msg.get_type() == "HEARTBEAT":
            self._last_heartbeat = time.time()
    def disconnect(self) -> None:
        if self.vehicle is not None:
            self.vehicle.close()
            self.vehicle = None
            logger.info("Disconnected from flight controller")
    def get_gps(self) -> Optional[Dict]:
        if not self.is_connected():
            logger.warning("get_gps: not connected")
            return None
        try:
            msg = self.vehicle.recv_match(type="GPS_RAW_INT", blocking=True, timeout=3)
            if msg is None:
                logger.warning("get_gps: no message received within timeout")
                return None
            return {
                "lat": msg.lat / 1e7,              
                "lon": msg.lon / 1e7,
                "alt_msl": msg.alt / 1e3,           
                "fix_type": msg.fix_type,
                "satellites_visible": msg.satellites_visible,
            }
        except Exception as exc:
            logger.error(f"get_gps error: {exc}")
            return None
    def get_altitude(self) -> Optional[Dict]:
        if not self.is_connected():
            return None
        try:
            msg = self.vehicle.recv_match(type="VFR_HUD", blocking=True, timeout=3)
            if msg is None:
                return None
            return {
                "alt_relative": msg.alt,
                "groundspeed": msg.groundspeed,
                "airspeed": msg.airspeed,
                "heading": msg.heading,
                "throttle": msg.throttle,
            }
        except Exception as exc:
            logger.error(f"get_altitude error: {exc}")
            return None
    def get_attitude(self) -> Optional[Dict]:
        if not self.is_connected():
            return None
        try:
            msg = self.vehicle.recv_match(type="ATTITUDE", blocking=True, timeout=3)
            if msg is None:
                return None
            return {
                "roll": math.degrees(msg.roll),
                "pitch": math.degrees(msg.pitch),
                "yaw": math.degrees(msg.yaw),
                "rollspeed": math.degrees(msg.rollspeed),
                "pitchspeed": math.degrees(msg.pitchspeed),
                "yawspeed": math.degrees(msg.yawspeed),
            }
        except Exception as exc:
            logger.error(f"get_attitude error: {exc}")
            return None
    def send_waypoint(self, lat: float, lon: float, alt: float) -> bool:
        if not self.is_connected():
            logger.error("send_waypoint: not connected")
            return False
        try:
            self.vehicle.mav.mission_item_int_send(
                self.vehicle.target_system,
                self.vehicle.target_component,
                0,                              
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                2,                              
                1,                              
                0, 0, 0, float("nan"),          
                int(lat * 1e7),                 
                int(lon * 1e7),                 
                alt,                            
            )
            logger.info(f"Waypoint sent: ({lat:.6f}, {lon:.6f}) alt={alt}m")
            return True
        except Exception as exc:
            logger.error(f"send_waypoint error: {exc}")
            return False
    def set_velocity(self, vx: float, vy: float, vz: float) -> bool:
        if not self.is_connected():
            logger.error("set_velocity: not connected")
            return False
        try:
            type_mask = (
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_X_IGNORE
                | mavutil.mavlink.POSITION_TARGET_TYPEMASK_Y_IGNORE
                | mavutil.mavlink.POSITION_TARGET_TYPEMASK_Z_IGNORE
                | mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE
                | mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE
                | mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE
                | mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE
                | mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE
            )
            self.vehicle.mav.set_position_target_local_ned_send(
                0,                              
                self.vehicle.target_system,
                self.vehicle.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                type_mask,
                0, 0, 0,                        
                vx, vy, vz,                     
                0, 0, 0,                        
                0, 0,                           
            )
            return True
        except Exception as exc:
            logger.error(f"set_velocity error: {exc}")
            return False
    def set_guided_mode(self) -> bool:
        if not self.is_connected():
            return False
        try:
            self.vehicle.set_mode("GUIDED")
            logger.info("Flight mode set to GUIDED")
            return True
        except Exception as exc:
            logger.error(f"set_guided_mode error: {exc}")
            return False
    def arm(self) -> bool:
        if not self.is_connected():
            return False
        try:
            self.vehicle.arducopter_arm()
            self.vehicle.motors_armed_wait()
            logger.info("Vehicle armed successfully")
            return True
        except Exception as exc:
            logger.error(f"arm error: {exc}")
            return False
