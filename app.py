import os
from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, atan2

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
        "lat": 18.254166,
        "lon": 42.748861,
        "radius": 250,
    },
    {
        "name": "مكان توقف للسائقين",
        "lat": 18.252444,
        "lon": 42.752450,
        "radius": 250,
    },
    {
        "name": "مطعم لكل السائقين",
        "lat": 18.244783,
        "lon": 42.736450,
        "radius": 250,
    },
    {
        "name": "مطعم 2 لكل السائقين",
        "lat": 18.253472,
        "lon": 42.753461,
        "radius": 250,
    },
    {
        "name": "مطعم 3 وورشة لكل السائقين",
        "lat": 18.336114,
        "lon": 42.733892,
        "radius": 250,
    },
    {
        "name": "ورشة لكل السائقين",
        "lat": 18.211503,
        "lon": 42.783725,
        "radius": 250,
    },
    {
        "name": "موقع انتظار للسائقين",
        "lat": 18.252450,
        "lon": 42.749047,
        "radius": 250,
    },
    {
        "name": "ورشة",
        "lat": 18.386911,
        "lon": 42.702189,
        "radius": 250,
    },
    {
        "name": "ورشة رافعات",
        "lat": 18.390703,
        "lon": 42.723897,
        "radius": 250,
    },
]


# =========================================================
# حساب المسافة بين نقطتين GPS
# =========================================================
def distance_meters(lat1, lon1, lat2, lon2):

    earth_radius = 6371000

    p1 = radians(lat1)
    p2 = radians(lat2)

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(p1)
        * cos(p2)
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return earth_radius * c


# =========================================================
# حساب عمر بيانات GPS
# =========================================================
def gps_age_minutes(datetime_text):

    if not datetime_text:
        return None

    try:

        dt = datetime.fromisoformat(
            datetime_text.replace(
                "Z",
                "+00:00"
            )
        )

        now = datetime.now(
            timezone.utc
        )

        age = (
            now - dt
        ).total_seconds() / 60

        return round(
            max(age, 0),
            1
        )

    except Exception:

        return None


# =========================================================
# جلب آخر إحداثيات المركبات
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
            "api_key": API_KEY,
        },
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# جلب Objects الرسمي - للاختبار
# =========================================================
def get_objects():

    if not API_KEY:

        raise RuntimeError(
            "TRUSTTRACK_API_KEY is not configured"
        )

    response = requests.get(
        f"{BASE_URL}/objects",
        params={
            "version": 1,
            "api_key": API_KEY,
        },
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# تحديد أقرب موقع معروف
# =========================================================
def find_known_location(lat, lon):

    if lat is None or lon is None:

        return None, None

    nearest_name = None
    nearest_distance = None

    for location in KNOWN_LOCATIONS:

        distance = distance_meters(
            lat,
            lon,
            location["lat"],
            location["lon"],
        )

        if (
            nearest_distance is None
            or distance < nearest_distance
        ):

            nearest_distance = distance
            nearest_name = location["name"]

    return (
        nearest_name,
        nearest_distance
    )


# =========================================================
# تحليل حالة الحركة
#
# ملاحظة:
# objects-last-coordinate لا يعطينا حتى الآن vehicleStatus
# الذي رأيناه في واجهة TrustTrack.
# لذلك لا نخمن حالة المحرك من السرعة وحدها.
# =========================================================
def analyze_movement(coord, age):

    raw_status = str(
        coord.get(
            "movement_status"
        )
        or ""
    ).lower()

    # إذا كانت بيانات GPS قديمة
    if age is None or age > 10:

        return (
            "stale",
            "بيانات GPS قديمة"
        )

    # إذا وصلنا مستقبلاً إلى حالة MOVING
    if raw_status == "moving":

        return (
            "moving",
            "متحرك الآن"
        )

    # حالات توقف محتملة
    if raw_status in [
        "stopped",
        "stop",
        "stationary",
        "idle",
        "parking",
        "parked",
        "ignition_off",
    ]:

        return (
            "stopped",
            "متوقف الآن"
        )

    # لا نخمن الحالة من السرعة
    return (
        "unknown",
        "حالة الحركة غير معروفة"
    )


# =========================================================
# تجهيز بيانات المركبات
# =========================================================
def prepare_vehicle_data():

    data = get_vehicles()

    vehicles = []

    for vehicle in data.get(
        "results",
        []
    ):

        coord = (
            vehicle.get(
                "last_coordinate"
            )
            or {}
        )

        lat = coord.get(
            "latitude"
        )

        lon = coord.get(
            "longitude"
        )

        speed = coord.get(
            "speed"
        )

        dt = coord.get(
            "datetime"
        )

        age = gps_age_minutes(
            dt
        )

        (
            location_name,
            distance
        ) = find_known_location(
            lat,
            lon,
        )

        known_location = False

        if distance is not None:

            for location in KNOWN_LOCATIONS:

                if (
                    location["name"]
                    == location_name
                    and distance
                    <= location["radius"]
                ):

                    known_location = True
                    break

        (
            movement_code,
            movement_text
        ) = analyze_movement(
            coord,
            age,
        )

        vehicles.append(
            {
                "name":
                    vehicle.get("name"),

                "speed":
                    speed,

                "latitude":
                    lat,

                "longitude":
                    lon,

                "datetime":
                    dt,

                "gps_age_minutes":
                    age,

                "movement_status":
                    movement_code,

                "movement_text":
                    movement_text,

                "raw_movement_status":
                    coord.get(
                        "movement_status"
                    ),

                "known_location":
                    known_location,

                "location":
                    (
                        location_name
                        if known_location
                        else
                        "خارج المواقع المعروفة"
                    ),

                "nearest_location":
                    location_name,

                "distance_meters":
                    (
                        round(distance)
                        if distance is not None
                        else None
                    ),
            }
        )

    return vehicles


# =========================================================
# الصفحة الرئيسية API
# =========================================================
@app.route("/")
def home():

    try:

        vehicles = (
            prepare_vehicle_data()
        )

        return jsonify(
            {
                "status":
                    "Forklift AI Agent is running",

                "vehicles_count":
                    len(vehicles),

                "vehicles":
                    vehicles,
            }
        )

    except Exception as error:

        return (
            jsonify(
                {
                    "status":
                        "error",

                    "message":
                        str(error),
                }
            ),
            500,
        )


# =========================================================
# Health Check
# =========================================================
@app.route("/health")
def health():

    return jsonify(
        {
            "status": "ok"
        }
    )


# =========================================================
# اختبار Object API الرسمي
#
# هذا المسار لا يعرض API KEY
# =========================================================
@app.route("/test-objects")
def test_objects():

    try:

        data = get_objects()

        return jsonify(
            {
                "status": "ok",
                "source": "TrustTrack Objects API",
                "data": data,
            }
        )

    except requests.exceptions.HTTPError as error:

        status_code = (
            error.response.status_code
            if error.response is not None
            else 500
        )

        return (
            jsonify(
                {
                    "status":
                        "error",

                    "type":
                        "HTTPError",

                    "http_status":
                        status_code,

                    "message":
                        str(error),
                }
            ),
            status_code,
        )

    except Exception as error:

        return (
            jsonify(
                {
                    "status":
                        "error",

                    "message":
                        str(error),
                }
            ),
            500,
        )


# =========================================================
# Dashboard
# =========================================================
@app.route("/dashboard")
def dashboard():

    try:

        vehicles = (
            prepare_vehicle_data()
        )

        html = """
<!DOCTYPE html>

<html lang="ar" dir="rtl">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<meta
    http-equiv="refresh"
    content="30"
>

<title>
مركز متابعة السائقين
</title>

<style>

body {
    margin: 0;
    font-family:
        Arial,
        Tahoma,
        sans-serif;
    background: #f1f5f9;
    color: #0f172a;
}

.header {
    background: #14213d;
    color: white;
    padding: 28px 6%;
}

.header h1 {
    margin: 0 0 10px 0;
}

.summary {
    margin: 28px 6%;
    background: white;
    padding: 20px;
    border-radius: 18px;
}

.grid {
    margin: 0 6% 40px 6%;
    display: grid;
    grid-template-columns:
        repeat(
            auto-fit,
            minmax(360px, 1fr)
        );
    gap: 20px;
}

.card {
    background: white;
    border-radius: 18px;
    padding: 22px;
    border-top:
        5px solid #2563eb;
}

.name {
    font-size: 28px;
    font-weight: bold;
    margin-bottom: 15px;
}

.badge {
    display: inline-block;
    padding: 9px 15px;
    border-radius: 30px;
    font-weight: bold;
    margin-bottom: 15px;
}

.moving {
    background: #dcfce7;
    color: #047857;
}

.stopped {
    background: #e2e8f0;
    color: #334155;
}

.stale {
    background: #fef3c7;
    color: #92400e;
}

.unknown {
    background: #fee2e2;
    color: #991b1b;
}

.row {
    display: flex;
    justify-content:
        space-between;
    gap: 20px;
    border-bottom:
        1px solid #e2e8f0;
    padding: 11px 0;
}

.label {
    color: #64748b;
}

.value {
    font-weight: bold;
    text-align: left;
}

.warning {
    color: #dc2626;
}

.test-link {
    display: inline-block;
    margin-top: 12px;
    padding: 10px 16px;
    background: #2563eb;
    color: white;
    text-decoration: none;
    border-radius: 10px;
    font-weight: bold;
}

</style>

</head>

<body>

<div class="header">

<h1>
مركز متابعة السائقين
</h1>

<div>
Forklift AI Agent —
متابعة مباشرة من TrustTrack
</div>

</div>


<div class="summary">

عدد المركبات المتصلة:

<strong>
{{ vehicles|length }}
</strong>

&nbsp;&nbsp; | &nbsp;&nbsp;

يتم تحديث اللوحة
تلقائياً كل 30 ثانية

<br>

<a
    class="test-link"
    href="/test-objects"
    target="_blank"
>
اختبار Objects API
</a>

</div>


<div class="grid">

{% for v in vehicles %}

<div class="card">

<div class="name">
{{ v.name }}
</div>


<div class="badge {{ v.movement_status }}">

● {{ v.movement_text }}

</div>


<div class="row">

<span class="label">
آخر سرعة مسجلة
</span>

<span class="value">

{{ v.speed if v.speed is not none else 0 }}
كم/س

</span>

</div>


<div class="row">

<span class="label">
الموقع
</span>

{% if v.known_location %}

<span class="value">
{{ v.location }}
</span>

{% else %}

<span class="value warning">
خارج المواقع المعروفة
</span>

{% endif %}

</div>


<div class="row">

<span class="label">
أقرب موقع مسجل
</span>

<span class="value">

{{ v.nearest_location or "غير معروف" }}

</span>

</div>


<div class="row">

<span class="label">
المسافة لأقرب موقع
</span>

<span class="value">

{% if v.distance_meters is not none %}

{{ v.distance_meters }}
متر

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

{{ v.datetime or "غير متوفر" }}

</span>

</div>


<div class="row">

<span class="label">
عمر بيانات GPS
</span>

<span class="value">

{% if v.gps_age_minutes is not none %}

{{ v.gps_age_minutes }}
دقيقة

{% else %}

غير معروف

{% endif %}

</span>

</div>


<div class="row">

<span class="label">
حالة TrustTrack الخام
</span>

<span class="value">

{{ v.raw_movement_status or "غير متوفرة" }}

</span>

</div>


<div class="row">

<span class="label">
خط العرض
</span>

<span class="value">

{{ v.latitude }}

</span>

</div>


<div class="row">

<span class="label">
خط الطول
</span>

<span class="value">

{{ v.longitude }}

</span>

</div>

</div>

{% endfor %}

</div>

</body>

</html>
"""

        return render_template_string(
            html,
            vehicles=vehicles,
        )

    except Exception as error:

        return f"""
        <html lang="ar" dir="rtl">
        <head>
        <meta charset="UTF-8">
        <title>خطأ</title>
        </head>
        <body>
        <h2>حدث خطأ</h2>
        <pre>{error}</pre>
        </body>
        </html>
        """, 500


# =========================================================
# تشغيل التطبيق
# =========================================================
if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                10000
            )
        ),
    )
