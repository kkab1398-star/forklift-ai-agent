import os
import math
import requests
from flask import Flask, jsonify

app = Flask(__name__)

API_KEY = os.environ.get("TRUSTTRACK_API_KEY")
BASE_URL = "https://api.fm-track.com"


# =========================================================
# المواقع المعروفة
# latitude, longitude, radius بالمتر
# =========================================================

KNOWN_LOCATIONS = [
    {
        "name": "سكن NAVEED",
        "latitude": 18.2337533,
        "longitude": 42.7429616,
        "radius": 180
    },
    {
        "name": "سكن WAHEED",
        "latitude": 18.2543166,
        "longitude": 42.7458916,
        "radius": 180
    },
    {
        "name": "مكان استراحة لكل السائقين",
        "latitude": 18.2546222,
        "longitude": 42.7488583,
        "radius": 180
    },
    {
        "name": "مكان توقف للسائقين",
        "latitude": 18.2529306,
        "longitude": 42.7520944,
        "radius": 180
    },
    {
        "name": "مطعم لكل السائقين",
        "latitude": 18.2454778,
        "longitude": 42.7364222,
        "radius": 180
    },
    {
        "name": "مطعم 2 لكل السائقين",
        "latitude": 18.2537083,
        "longitude": 42.7534611,
        "radius": 180
    },
    {
        "name": "مطعم 3 وورشة لكل السائقين",
        "latitude": 18.3361389,
        "longitude": 42.7366139,
        "radius": 200
    },
    {
        "name": "ورشة لكل السائقين",
        "latitude": 18.2615028,
        "longitude": 42.7837806,
        "radius": 200
    },
    {
        "name": "موقع انتظار للسائقين",
        "latitude": 18.2580056,
        "longitude": 42.7488528,
        "radius": 180
    },
    {
        "name": "ورشة",
        "latitude": 18.3913528,
        "longitude": 42.7030694,
        "radius": 200
    },
    {
        "name": "ورشة رافعات",
        "latitude": 18.3906194,
        "longitude": 42.7073694,
        "radius": 200
    }
]


# =========================================================
# حساب المسافة بين إحداثيين بالمتر
# =========================================================

def distance_meters(lat1, lon1, lat2, lon2):
    earth_radius = 6371000

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius * c


# =========================================================
# تحديد الموقع المعروف الأقرب
# =========================================================

def detect_location(latitude, longitude):
    if latitude is None or longitude is None:
        return {
            "known": False,
            "name": "الموقع غير متوفر",
            "distance_meters": None
        }

    nearest = None
    nearest_distance = None

    for location in KNOWN_LOCATIONS:
        distance = distance_meters(
            latitude,
            longitude,
            location["latitude"],
            location["longitude"]
        )

        if nearest_distance is None or distance < nearest_distance:
            nearest = location
            nearest_distance = distance

    if nearest and nearest_distance <= nearest["radius"]:
        return {
            "known": True,
            "name": nearest["name"],
            "distance_meters": round(nearest_distance)
        }

    return {
        "known": False,
        "name": "خارج المواقع المعروفة",
        "distance_meters": round(nearest_distance) if nearest_distance is not None else None
    }


# =========================================================
# جلب بيانات المركبات من TrustTrack
# =========================================================

def get_vehicles():
    if not API_KEY:
        raise RuntimeError("TRUSTTRACK_API_KEY is not configured")

    response = requests.get(
        f"{BASE_URL}/objects-last-coordinate",
        params={
            "version": 2,
            "api_key": API_KEY
        },
        timeout=20
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# الصفحة الرئيسية
# =========================================================

@app.route("/")
def home():
    try:
        data = get_vehicles()

        vehicles = []

        for vehicle in data.get("results", []):
            coord = vehicle.get("last_coordinate") or {}

            latitude = coord.get("latitude")
            longitude = coord.get("longitude")

            detected_location = detect_location(
                latitude,
                longitude
            )

            vehicles.append({
                "name": vehicle.get("name"),
                "speed": coord.get("speed"),
                "latitude": latitude,
                "longitude": longitude,
                "datetime": coord.get("datetime"),

                "location": detected_location["name"],
                "known_location": detected_location["known"],
                "distance_meters": detected_location["distance_meters"]
            })

        return jsonify({
            "status": "Forklift AI Agent is running",
            "vehicles_count": len(vehicles),
            "vehicles": vehicles
        })

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500


# =========================================================
# فحص الخدمة
# =========================================================

@app.route("/health")
def health():
    return jsonify({
        "status": "ok"
    })
