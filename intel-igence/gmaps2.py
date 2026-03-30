import numpy
import scipy

road = {
    "id": 101,
    "length": 120.5,  # meters
    "start": (12.9716, 77.6412),  # lat, lon
    "end": (12.9721, 77.6420),  # lat, lon
    "avg_elevation": 9.8
}

rain = 6

rain_presets = {
    "light": 3,
    "medium": 6,
    "heavy": 9

}


def rain_intensity(mode):
    return rain_presets[mode]


