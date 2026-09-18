import os
import math
import requests
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

API_KEY = os.environ.get("TRUSTTRACK_API_KEY")
BASE_URL = "https://api.fm-track.com"


# =========================================================
# المواقع المعروفة
# =========================================================

KNOWN_LOCATIONS = [
    {"name": "سكن NAVEED", "latitude": 18.2337533, "longitude": 42.7429616, "radius": 180},
    {"name": "سكن WAHEED", "latitude": 18.2543166, "longitude": 42.7458916, "radius": 180},

    {"name": "مكان استراحة لكل السائقين", "latitude": 18.2546222, "longitude": 42.7488583, "radius": 180},
    {"name": "مكان توقف للسائقين", "latitude": 18.2529306, "longitude": 42.7520944, "radius": 180},

    {"name": "مطعم لكل السائقين", "latitude": 18.2454778, "longitude": 42.7364222, "radius": 180},
    {"name": "مطعم 2 لكل السائقين", "latitude": 18.2537083, "longitude": 42.7534611, "radius": 180},
    {"name": "مطعم 3 وورشة لكل السائقين", "latitude": 18.3361389, "longitude": 42.7366139, "radius": 200},

    {"name": "ورشة لكل السائقين", "latitude": 18.2615028, "longitude": 42.7837806, "radius": 200},
    {"name": "موقع انتظار للسائقين", "latitude": 18.2580056, "longitude": 42.7488528, "radius": 180},

    {"name": "ورشة", "latitude": 18.3913528, "longitude": 42.7030694, "radius": 200},
    {"name": "ورشة رافعات", "latitude": 18.3906194, "longitude": 42.7073694, "radius": 200}
]


# =========================================================
# حساب المسافة
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
# التعرف على الموقع
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
# TrustTrack
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


def build_vehicle_list():
    data = get_vehicles()
    vehicles = []

    for vehicle in data.get("results", []):
        coord = vehicle.get("last_coordinate") or {}

        latitude = coord.get("latitude")
        longitude = coord.get("longitude")
        speed = coord.get("speed") or 0

        location = detect_location(latitude, longitude)

        if speed > 3:
            movement_status = "متحرك"
        else:
            movement_status = "متوقف"

        vehicles.append({
            "name": vehicle.get("name") or "بدون اسم",
            "speed": speed,
            "latitude": latitude,
            "longitude": longitude,
            "datetime": coord.get("datetime"),
            "location": location["name"],
            "known_location": location["known"],
            "distance_meters": location["distance_meters"],
            "movement_status": movement_status
        })

    return vehicles


# =========================================================
# API JSON
# =========================================================

@app.route("/")
def home():
    try:
        vehicles = build_vehicle_list()

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
# لوحة التحكم العربية
# =========================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <title>مركز متابعة السائقين</title>

    <meta http-equiv="refresh" content="30">

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: Arial, Tahoma, sans-serif;
            background: #f3f5f8;
            color: #172033;
        }

        .header {
            background: #172033;
            color: white;
            padding: 24px 6%;
        }

        .header h1 {
            margin: 0 0 8px 0;
            font-size: 28px;
        }

        .header p {
            margin: 0;
            color: #cbd3df;
        }

        .container {
            width: 90%;
            max-width: 1200px;
            margin: 28px auto;
        }

        .summary {
            background: white;
            border-radius: 14px;
            padding: 18px 22px;
            margin-bottom: 22px;
            box-shadow: 0 4px 18px rgba(0,0,0,.06);
        }

        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
        }

        .card {
            background: white;
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 4px 18px rgba(0,0,0,.07);
            border-top: 5px solid #2d6cdf;
        }

        .driver-name {
            font-size: 25px;
            font-weight: bold;
            margin-bottom: 16px;
        }

        .status {
            display: inline-block;
            padding: 7px 13px;
            border-radius: 20px;
            font-weight: bold;
            margin-bottom: 15px;
        }

        .moving {
            background: #e5f8ec;
            color: #147a3e;
        }

        .stopped {
            background: #fff0e7;
            color: #a34a16;
        }

        .row {
            border-bottom: 1px solid #edf0f4;
            padding: 11px 0;
            display: flex;
            justify-content: space-between;
            gap: 15px;
        }

        .row:last-child {
            border-bottom: none;
        }

        .label {
            color: #687386;
        }

        .value {
            font-weight: bold;
            text-align: left;
        }

        .known {
            color: #147a3e;
        }

        .unknown {
            color: #b23b3b;
        }

        .footer {
            text-align: center;
            color: #7b8494;
            padding: 30px;
            font-size: 13px;
        }

    </style>
</head>

<body>

<div class="header">
    <h1>مركز متابعة السائقين</h1>
    <p>Forklift AI Agent — متابعة مباشرة من TrustTrack</p>
</div>

<div class="container">

    <div class="summary">
        عدد المركبات المتصلة:
        <strong>{{ vehicles|length }}</strong>
        &nbsp; | &nbsp;
        يتم تحديث اللوحة تلقائيًا كل 30 ثانية
    </div>

    <div class="cards">

        {% for vehicle in vehicles %}

        <div class="card">

            <div class="driver-name">
                {{ vehicle.name }}
            </div>

            {% if vehicle.movement_status == "متحرك" %}
                <div class="status moving">● متحرك</div>
            {% else %}
                <div class="status stopped">● متوقف</div>
            {% endif %}

            <div class="row">
                <span class="label">السرعة</span>
                <span class="value">{{ vehicle.speed }} كم/س</span>
            </div>

            <div class="row">
                <span class="label">الموقع</span>

                {% if vehicle.known_location %}
                    <span class="value known">
                        {{ vehicle.location }}
                    </span>
                {% else %}
                    <span class="value unknown">
                        {{ vehicle.location }}
                    </span>
                {% endif %}
            </div>

            <div class="row">
                <span class="label">المسافة لأقرب موقع مسجل</span>
                <span class="value">
                    {% if vehicle.distance_meters is not none %}
                        {{ vehicle.distance_meters }} متر
                    {% else %}
                        غير متوفر
                    {% endif %}
                </span>
            </div>

            <div class="row">
                <span class="label">آخر تحديث GPS</span>
                <span class="value">
                    {{ vehicle.datetime or "غير متوفر" }}
                </span>
            </div>

            <div class="row">
                <span class="label">خط العرض</span>
                <span class="value">{{ vehicle.latitude }}</span>
            </div>

            <div class="row">
                <span class="label">خط الطول</span>
                <span class="value">{{ vehicle.longitude }}</span>
            </div>

        </div>

        {% endfor %}

    </div>

</div>

<div class="footer">
    Forklift AI Agent
</div>

</body>
</html>
"""


@app.route("/dashboard")
def dashboard():
    try:
        vehicles = build_vehicle_list()

        return render_template_string(
            DASHBOARD_HTML,
            vehicles=vehicles
        )

    except Exception as error:
        return f"""
        <html dir="rtl">
        <body style="font-family:Arial;padding:40px">
            <h2>تعذر تحميل لوحة المتابعة</h2>
            <p>{str(error)}</p>
        </body>
        </html>
        """, 500


# =========================================================
# Health
# =========================================================

@app.route("/health")
def health():
    return jsonify({"status": "ok"})
