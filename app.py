import os
import math
import requests
from datetime import datetime, timezone
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


# =========================================================
# حساب المسافة بين نقطتين
# =========================================================

def distance_meters(lat1, lon1, lat2, lon2):

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

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius * c


# =========================================================
# تحديد حالة الحركة
# =========================================================

def get_movement_status(speed, gps_datetime):
    """
    لا نعتمد على السرعة وحدها.

    إذا كان آخر GPS قديماً، لا نقول إن المركبة تتحرك الآن
    حتى لو كانت آخر سرعة مسجلة أكبر من صفر.
    """

    if not gps_datetime:
        return {
            "status": "بيانات GPS غير متوفرة",
            "gps_age_minutes": None
        }

    try:

        gps_time = datetime.fromisoformat(
            gps_datetime.replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        age_minutes = (
            now - gps_time
        ).total_seconds() / 60

        # حماية في حال اختلاف الساعة
        if age_minutes < 0:
            age_minutes = 0

        speed_value = float(speed or 0)

        # آخر تحديث أقدم من 5 دقائق
        if age_minutes > 5:

            return {
                "status": "بيانات GPS قديمة",
                "gps_age_minutes": round(age_minutes, 1)
            }

        # 0 - 2 كم/س نعتبرها توقف
        # لتقليل تأثير اهتزاز GPS
        if speed_value <= 2:

            return {
                "status": "متوقف",
                "gps_age_minutes": round(age_minutes, 1)
            }

        return {
            "status": "متحرك",
            "gps_age_minutes": round(age_minutes, 1)
        }

    except Exception:

        return {
            "status": "حالة غير معروفة",
            "gps_age_minutes": None
        }


# =========================================================
# تحديد الموقع المعروف
# =========================================================

def identify_location(latitude, longitude):

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

        if (
            nearest_distance is None
            or distance < nearest_distance
        ):

            nearest_distance = distance
            nearest = place

    if (
        nearest
        and nearest_distance <= nearest["radius"]
    ):

        return {
            "location": nearest["name"],
            "known_location": True,
            "distance_meters": round(nearest_distance)
        }

    return {
        "location": "خارج المواقع المعروفة",
        "known_location": False,
        "distance_meters":
            round(nearest_distance)
            if nearest_distance is not None
            else None
    }


# =========================================================
# الاتصال بـ TrustTrack
# =========================================================

def get_vehicles():

    if not API_KEY:
        raise RuntimeError(
            "TRUSTTRACK_API_KEY is not configured"
        )

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
# تجهيز بيانات المركبات
# =========================================================

def build_vehicle_list():

    data = get_vehicles()

    vehicles = []

    for vehicle in data.get("results", []):

        coord = vehicle.get("last_coordinate") or {}

        latitude = coord.get("latitude")
        longitude = coord.get("longitude")
        speed = coord.get("speed")
        gps_datetime = coord.get("datetime")

        location_info = identify_location(
            latitude,
            longitude
        )

        movement_info = get_movement_status(
            speed,
            gps_datetime
        )

        vehicles.append({

            "name": vehicle.get("name"),

            "speed": speed,

            "latitude": latitude,

            "longitude": longitude,

            "datetime": gps_datetime,

            "movement_status":
                movement_info["status"],

            "gps_age_minutes":
                movement_info["gps_age_minutes"],

            "location":
                location_info["location"],

            "known_location":
                location_info["known_location"],

            "distance_meters":
                location_info["distance_meters"]
        })

    return vehicles


# =========================================================
# API الرئيسية
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
# فحص الخدمة
# =========================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok"
    })


# =========================================================
# لوحة المتابعة
# =========================================================

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

<meta name="viewport"
content="width=device-width, initial-scale=1">

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
    grid-template-columns:
        repeat(auto-fit,minmax(360px,1fr));
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

.status {
    display: inline-block;
    padding: 8px 15px;
    border-radius: 30px;
    font-weight: bold;
    margin-bottom: 10px;
}

.moving {
    background: #dcfce7;
    color: #08783d;
}

.stopped {
    background: #e5e7eb;
    color: #374151;
}

.old {
    background: #fef3c7;
    color: #92400e;
}

.unknown-status {
    background: #fee2e2;
    color: #991b1b;
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
    gap: 20px;
    border-bottom: 1px solid #e5e7eb;
    padding: 12px 0;
}

.label {
    color: #667085;
}

.value {
    font-weight: bold;
    text-align: left;
}

</style>

</head>

<body>

<header>

<h1>
مركز متابعة السائقين
</h1>

<p>
Forklift AI Agent —
متابعة مباشرة من TrustTrack
</p>

</header>


<div class="container">


<div class="summary">

عدد المركبات المتصلة:

<strong>
{{ vehicles|length }}
</strong>

&nbsp;&nbsp; | &nbsp;&nbsp;

يتم تحديث اللوحة تلقائياً كل 30 ثانية

</div>


<div class="grid">


{% for vehicle in vehicles %}


<div class="card">


<div class="name">
{{ vehicle.name }}
</div>


{% if vehicle.movement_status == "متحرك" %}

<span class="status moving">
● متحرك الآن
</span>

{% elif vehicle.movement_status == "متوقف" %}

<span class="status stopped">
● متوقف
</span>

{% elif vehicle.movement_status == "بيانات GPS قديمة" %}

<span class="status old">
● بيانات GPS قديمة
</span>

{% else %}

<span class="status unknown-status">
● {{ vehicle.movement_status }}
</span>

{% endif %}


<div class="row">

<span class="label">
آخر سرعة مسجلة
</span>

<span class="value">
{{ vehicle.speed if vehicle.speed is not none else 0 }}
كم/س
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

{% if vehicle.distance_meters is not none %}

{{ vehicle.distance_meters }} متر

{% else %}

غير متوفر

{% endif %}

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
عمر بيانات GPS
</span>

<span class="value">

{% if vehicle.gps_age_minutes is not none %}

{{ vehicle.gps_age_minutes }} دقيقة

{% else %}

غير متوفر

{% endif %}

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
        <html lang="ar" dir="rtl">
        <body>
        <h2>حدث خطأ</h2>
        <p>{error}</p>
        </body>
        </html>
        """, 500


# =========================================================
# تشغيل محلي
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
