import struct
import time
import logging
from typing import Any, Dict, List, Optional
import serial
logger = logging.getLogger(__name__)
class LDRobotD500:
    FRAME_HEADER: int = 0x54
    FRAME_TYPE: int = 0x2C        
    BAUD_RATE: int = 230_400
    FRAME_SIZE: int = 47
    POINTS_PER_FRAME: int = 12
    def __init__(self, port: str = "/dev/ttyUSB0") -> None:
        self.port = port
        self._serial: Optional[serial.Serial] = None
        self._connected: bool = False
    def connect(self) -> bool:
        try:
            self._serial = serial.Serial(
                self.port,
                baudrate=self.BAUD_RATE,
                timeout=1.0,
            )
            self._connected = True
            logger.info(f"LDRobot D500 connected on {self.port}")
            return True
        except serial.SerialException as exc:
            logger.error(f"LDRobot D500 connect failed: {exc}")
            return False
    def _parse_frame(self, data: bytes) -> Optional[Dict]:
        if len(data) < self.FRAME_SIZE:
            return None
        if data[0] != self.FRAME_HEADER or data[1] != self.FRAME_TYPE:
            return None
        speed_rpm = struct.unpack_from("<H", data, 2)[0] / 100.0
        start_angle = struct.unpack_from("<H", data, 4)[0] / 100.0   
        end_angle = struct.unpack_from("<H", data, 40)[0] / 100.0
        timestamp_ms = struct.unpack_from("<H", data, 42)[0]
        points: List[Dict] = []
        for i in range(self.POINTS_PER_FRAME):
            offset = 6 + i * 3
            distance_mm = struct.unpack_from("<H", data, offset)[0]
            intensity = data[offset + 2]
            points.append({"distance_mm": distance_mm, "intensity": intensity})
        n = len(points) - 1
        if start_angle <= end_angle:
            step = (end_angle - start_angle) / n if n > 0 else 0
        else:
            step = (end_angle + 360.0 - start_angle) / n if n > 0 else 0
        for i, pt in enumerate(points):
            pt["angle"] = (start_angle + i * step) % 360.0
        return {
            "speed_rpm": speed_rpm,
            "start_angle": start_angle,
            "end_angle": end_angle,
            "timestamp_ms": timestamp_ms,
            "points": points,
        }
    def read_scan(self) -> Optional[Dict[str, Any]]:
        if not self._connected or self._serial is None:
            logger.warning("LDRobot D500 not connected")
            return None
        all_points: List[Dict] = []
        frames_collected = 0
        deadline = time.time() + 2.0
        while frames_collected < 30 and time.time() < deadline:
            byte = self._serial.read(1)
            if not byte or byte[0] != self.FRAME_HEADER:
                continue
            rest = self._serial.read(self.FRAME_SIZE - 1)
            if len(rest) < self.FRAME_SIZE - 1:
                continue
            frame = byte + rest
            parsed = self._parse_frame(frame)
            if parsed:
                all_points.extend(parsed["points"])
                frames_collected += 1
        if not all_points:
            logger.warning("LDRobot D500 returned no valid frames")
            return None
        return {
            "sensor": "ldrobot_d500",
            "timestamp": time.time(),
            "frame_count": frames_collected,
            "point_count": len(all_points),
            "points": all_points,
        }
    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False
        logger.info("LDRobot D500 disconnected")
class TFLuna:
    FRAME_HEADER: int = 0x59
    BAUD_RATE: int = 115_200
    FRAME_SIZE: int = 9
    def __init__(self, port: str = "/dev/ttyAMA1") -> None:
        self.port = port
        self._serial: Optional[serial.Serial] = None
        self._connected: bool = False
    def connect(self) -> bool:
        try:
            self._serial = serial.Serial(
                self.port,
                baudrate=self.BAUD_RATE,
                timeout=1.0,
            )
            self._connected = True
            logger.info(f"TF-Luna connected on {self.port}")
            return True
        except serial.SerialException as exc:
            logger.error(f"TF-Luna connect failed: {exc}")
            return False
    @staticmethod
    def _checksum(frame: bytes) -> int:
        return sum(frame[:8]) & 0xFF
    def read_distance(self) -> Optional[Dict[str, Any]]:
        if not self._connected or self._serial is None:
            logger.warning("TF-Luna not connected")
            return None
        try:
            while True:
                b1 = self._serial.read(1)
                if not b1:
                    return None
                if b1[0] != self.FRAME_HEADER:
                    continue
                b2 = self._serial.read(1)
                if not b2:
                    return None
                if b2[0] == self.FRAME_HEADER:
                    break   
            body = self._serial.read(self.FRAME_SIZE - 2)
            if len(body) < self.FRAME_SIZE - 2:
                logger.warning("TF-Luna: incomplete frame")
                return None
            frame = b1 + b2 + body
            if self._checksum(frame) != frame[8]:
                logger.warning("TF-Luna checksum mismatch — discarding frame")
                return None
            distance_cm: int = struct.unpack_from("<H", frame, 2)[0]
            amplitude: int = struct.unpack_from("<H", frame, 4)[0]
            temp_raw: int = struct.unpack_from("<H", frame, 6)[0]
            chip_temp_c: float = temp_raw / 8.0 - 256.0
            valid = 100 <= amplitude <= 65_000
            return {
                "sensor": "tf_luna",
                "timestamp": time.time(),
                "distance_cm": distance_cm if valid else None,
                "distance_m": distance_cm / 100.0 if valid else None,
                "amplitude": amplitude,
                "chip_temp_c": round(chip_temp_c, 1),
                "valid": valid,
            }
        except Exception as exc:
            logger.error(f"TF-Luna read error: {exc}")
            return None
    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False
        logger.info("TF-Luna disconnected")
class SensorManager:
    def __init__(self, d500_port: str, tf_luna_port: str) -> None:
        self.d500 = LDRobotD500(port=d500_port)
        self.tf_luna = TFLuna(port=tf_luna_port)
    def initialize(self) -> Dict[str, bool]:
        return {
            "d500": self.d500.connect(),
            "tf_luna": self.tf_luna.connect(),
        }
    def read_lidar(self) -> Optional[Dict[str, Any]]:
        return self.d500.read_scan()
    def read_tf_luna(self) -> Optional[Dict[str, Any]]:
        return self.tf_luna.read_distance()
    def read_all(self) -> Dict[str, Any]:
        return {
            "lidar_360": self.read_lidar(),
            "lidar_front": self.read_tf_luna(),
            "timestamp": time.time(),
        }
    def shutdown(self) -> None:
        self.d500.disconnect()
        self.tf_luna.disconnect()
        logger.info("All sensors disconnected")
