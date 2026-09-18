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
    {
        "name": "مكان استراحة لكل السائقين",
        "latitude": 18.2545556,
        "longitude": 42.7488583,
        "radius": 150
    },
    {
        "name": "مكان توقف للسائقين",
        "latitude": 18.2524111,
        "longitude": 42.7523722,
        "radius": 150
    },
    {
        "name": "مطعم لكل السائقين",
        "latitude": 18.2454778,
        "longitude": 42.7364222,
        "radius": 150
    },
    {
        "name": "مطعم 2 لكل السائقين",
        "latitude": 18.2534722,
        "longitude": 42.7534611,
        "radius": 150
    },
    {
        "name": "مطعم 3 وورشة لكل السائقين",
        "latitude": 18.3361528,
        "longitude": 42.7338361,
        "radius": 150
    },
    {
        "name": "ورشة لكل السائقين",
        "latitude": 18.2534472,
        "longitude": 42.7837839,
        "radius": 150
    },
    {
        "name": "موقع انتظار للسائقين",
        "latitude": 18.2524500,
        "longitude": 42.7490500,
        "radius": 150
    },
    {
        "name": "ورشة",
        "latitude": 18.3869111,
        "longitude": 42.7035778,
        "radius": 150
    },
    {
        "name": "ورشة رافعات",
        "latitude": 18.3907028,
        "longitude": 42.7072861,
        "radius": 150
    }
]


def distance_meters(lat1, lon1, lat2, lon2):
    """حساب المسافة بين نقطتين بالمتر."""
    earth_radius = 6371000

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius * c


def identify_location(latitude, longitude):
    """
    يحدد أقرب موقع معروف.
    إذا كانت المركبة داخل نصف قطر الموقع يتم اعتبارها داخله.
    """

    if latitude is None or longitude is None:
        return {
            "location": "الموقع غير متوفر",
            "known_location": False,
            "distance_meters": None
        }

    nearest = None
    nearest_distance = None

    for place in KNOWN_LOCATIONS:

        distance = distance_meters(
            latitude,
            longitude,
            place["latitude"],
            place["longitude"]
        )

        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest = place

    if nearest and nearest_distance <= nearest["radius"]:
        return {
            "location": nearest["name"],
            "known_location": True,
            "distance_meters": round(nearest_distance)
        }

    return {
        "location": "خارج المواقع المعروفة",
        "known_location": False,
        "distance_meters": round(nearest_distance) if nearest_distance else None
    }


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

        location_info = identify_location(
            latitude,
            longitude
        )

        vehicles.append({
            "name": vehicle.get("name"),
            "speed": coord.get("speed"),
            "latitude": latitude,
            "longitude": longitude,
            "datetime": coord.get("datetime"),
            "location": location_info["location"],
            "known_location": location_info["known_location"],
            "distance_meters": location_info["distance_meters"]
        })

    return vehicles


@app.route("/")
def home():

    try:

        vehicles = build_vehicle_list()

        return jsonify({
            "status": "Forklift AI Agent is running",
            "vehicles": vehicles,
            "vehicles_count": len(vehicles)
        })

    except Exception as error:

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500


@app.route("/health")
def health():

    return jsonify({
        "status": "ok"
    })


@app.route("/dashboard")
def dashboard():

    try:

        vehicles = build_vehicle_list()

        html = """
<!DOCTYPE html>

<html lang="ar" dir="rtl">

<head>

<meta charset="UTF-8">

<meta http-equiv="refresh" content="30">

<meta name="viewport" content="width=device-width, initial-scale=1">

<title>مركز متابعة السائقين</title>

<style>

body {
    margin: 0;
    font-family: Arial, Tahoma, sans-serif;
    background: #f3f6fa;
    color: #111827;
}

header {
    background: #162136;
    color: white;
    padding: 25px 6%;
}

header h1 {
    margin: 0;
    font-size: 27px;
}

header p {
    margin-bottom: 0;
}

.container {
    width: 88%;
    margin: 28px auto;
}

.summary {
    background: white;
    padding: 20px;
    border-radius: 16px;
    margin-bottom: 22px;
    box-shadow: 0 5px 20px rgba(0,0,0,.04);
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit,minmax(360px,1fr));
    gap: 20px;
}

.card {
    background: white;
    border-radius: 17px;
    padding: 22px;
    border-top: 5px solid #2f6fed;
    box-shadow: 0 5px 20px rgba(0,0,0,.06);
}

.name {
    font-size: 27px;
    font-weight: bold;
    margin-bottom: 15px;
}

.moving {
    display: inline-block;
    background: #dcfce7;
    color: #08783d;
    padding: 8px 15px;
    border-radius: 30px;
    font-weight: bold;
}

.stopped {
    display: inline-block;
    background: #f3f4f6;
    padding: 8px 15px;
    border-radius: 30px;
    font-weight: bold;
}

.known {
    color: #08783d;
    font-weight: bold;
}

.unknown {
    color: #c62828;
    font-weight: bold;
}

.row {
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid #e5e7eb;
    padding: 12px 0;
}

.label {
    color: #667085;
}

.value {
    font-weight: bold;
}

</style>

</head>

<body>

<header>

<h1>مركز متابعة السائقين</h1>

<p>Forklift AI Agent — متابعة مباشرة من TrustTrack</p>

</header>

<div class="container">

<div class="summary">

عدد المركبات المتصلة:
<strong>{{ vehicles|length }}</strong>

&nbsp;&nbsp; | &nbsp;&nbsp;

يتم تحديث اللوحة تلقائياً كل 30 ثانية

</div>

<div class="grid">

{% for vehicle in vehicles %}

<div class="card">

<div class="name">
{{ vehicle.name }}
</div>

{% if vehicle.speed and vehicle.speed > 0 %}

<span class="moving">
● متحرك
</span>

{% else %}

<span class="stopped">
● متوقف
</span>

{% endif %}

<div class="row">

<span class="label">
السرعة
</span>

<span class="value">
{{ vehicle.speed }} كم/س
</span>

</div>

<div class="row">

<span class="label">
الموقع
</span>

{% if vehicle.known_location %}

<span class="known">
{{ vehicle.location }}
</span>

{% else %}

<span class="unknown">
{{ vehicle.location }}
</span>

{% endif %}

</div>

<div class="row">

<span class="label">
المسافة لأقرب موقع مسجل
</span>

<span class="value">
{{ vehicle.distance_meters }} متر
</span>

</div>

<div class="row">

<span class="label">
آخر تحديث GPS
</span>

<span class="value">
{{ vehicle.datetime }}
</span>

</div>

<div class="row">

<span class="label">
خط العرض
</span>

<span class="value">
{{ vehicle.latitude }}
</span>

</div>

<div class="row">

<span class="label">
خط الطول
</span>

<span class="value">
{{ vehicle.longitude }}
</span>

</div>

</div>

{% endfor %}

</div>

</div>

</body>

</html>
"""

        return render_template_string(
            html,
            vehicles=vehicles
        )

    except Exception as error:

        return f"""
        <h2>حدث خطأ</h2>
        <p>{error}</p>
        """, 500
