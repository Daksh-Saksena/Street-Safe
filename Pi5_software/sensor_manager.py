import struct
import time
import serial
class LDRobotD500:
    FRAME_HEADER = 0x54
    FRAME_TYPE = 0x2C
    BAUD_RATE = 230_400
    FRAME_SIZE = 47
    POINTS_PER_FRAME = 12
    def __init__(self, port="/dev/ttyUSB0"):
        self.port = port
        self._serial = None
        self._connected = False
    def connect(self):
        try:
            self._serial = serial.Serial(self.port, baudrate=self.BAUD_RATE, timeout=1.0)
            self._connected = True
            return True
        except serial.SerialException as e:
            print(f"D500 connect failed: {e}")
            return False
    def _parse_frame(self, data):
        if len(data) < self.FRAME_SIZE:
            return None
        if data[0] != self.FRAME_HEADER or data[1] != self.FRAME_TYPE:
            return None
        rpm = struct.unpack_from("<H", data, 2)[0] / 100.0
        a0 = struct.unpack_from("<H", data, 4)[0] / 100.0
        a1 = struct.unpack_from("<H", data, 40)[0] / 100.0
        ts = struct.unpack_from("<H", data, 42)[0]
        pts = []
        for i in range(self.POINTS_PER_FRAME):
            offset = 6 + i * 3
            pts.append({"distance_mm": struct.unpack_from("<H", data, offset)[0], "intensity": data[offset + 2]})
        n = len(pts) - 1
        step = ((a1 - a0) if a0 <= a1 else (a1 + 360.0 - a0)) / n if n > 0 else 0
        for i, pt in enumerate(pts):
            pt["angle"] = (a0 + i * step) % 360.0
        return {"speed_rpm": rpm, "start_angle": a0, "end_angle": a1, "timestamp_ms": ts, "points": pts}
    def read_scan(self):
        if not self._connected or self._serial is None:
            return None
        pts = []
        frames = 0
        end = time.time() + 2.0
        while frames < 30 and time.time() < end:
            b = self._serial.read(1)
            if not b or b[0] != self.FRAME_HEADER:
                continue
            rest = self._serial.read(self.FRAME_SIZE - 1)
            if len(rest) < self.FRAME_SIZE - 1:
                continue
            parsed = self._parse_frame(b + rest)
            if parsed:
                pts.extend(parsed["points"])
                frames += 1
        if not pts:
            return None
        return {
            "sensor": "ldrobot_d500",
            "timestamp": time.time(),
            "frame_count": frames,
            "point_count": len(pts),
            "points": pts,
        }
    def disconnect(self):
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False
class TFLuna:
    FRAME_HEADER = 0x59
    BAUD_RATE = 115_200
    FRAME_SIZE = 9
    def __init__(self, port="/dev/ttyAMA1"):
        self.port = port
        self._serial = None
        self._connected = False
    def connect(self):
        try:
            self._serial = serial.Serial(self.port, baudrate=self.BAUD_RATE, timeout=1.0)
            self._connected = True
            return True
        except serial.SerialException as e:
            print(f"TF-Luna connect failed: {e}")
            return False
    @staticmethod
    def _checksum(frame):
        return sum(frame[:8]) & 0xFF
    def read_distance(self):
        if not self._connected or self._serial is None:
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
                return None
            frame = b1 + b2 + body
            if self._checksum(frame) != frame[8]:
                return None
            dcm = struct.unpack_from("<H", frame, 2)[0]
            amp = struct.unpack_from("<H", frame, 4)[0]
            temp = struct.unpack_from("<H", frame, 6)[0] / 8.0 - 256.0
            valid = 100 <= amp <= 65_000
            return {
                "sensor": "tf_luna",
                "timestamp": time.time(),
                "distance_cm": dcm if valid else None,
                "distance_m": dcm / 100.0 if valid else None,
                "amplitude": amp,
                "chip_temp_c": round(temp, 1),
                "valid": valid,
            }
        except Exception as e:
            print(f"TF-Luna read error: {e}")
            return None
    def disconnect(self):
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False
class SensorManager:
    def __init__(self, d500_port, tf_luna_port):
        self.d500 = LDRobotD500(port=d500_port)
        self.tf_luna = TFLuna(port=tf_luna_port)
    def initialize(self):
        return {"d500": self.d500.connect(), "tf_luna": self.tf_luna.connect()}
    def read_lidar(self):
        return self.d500.read_scan()
    def read_tf_luna(self):
        return self.tf_luna.read_distance()
    def read_all(self):
        return {"lidar_360": self.read_lidar(), "lidar_front": self.read_tf_luna(), "timestamp": time.time()}
    def shutdown(self):
        self.d500.disconnect()
        self.tf_luna.disconnect()
