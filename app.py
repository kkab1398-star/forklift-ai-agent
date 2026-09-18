import os
import json
from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, atan2

import requests
from flask import Flask, jsonify, render_template_string


app = Flask(__name__)

API_KEY = os.environ.get("TRUSTTRACK_API_KEY")
BASE_URL = "https://api.fm-track.com"

# =========================================================
# إعدادات تحليل الحركة
# =========================================================

# إذا تحركت المركبة أكثر من هذه المسافة نعتبرها حركة حقيقية
MOVEMENT_DISTANCE_METERS = 25

# بعد كم دقيقة من عدم وجود حركة نعتبر المركبة متوقفة
STOP_AFTER_MINUTES = 5

# إذا كانت بيانات GPS أقدم من هذا الحد نعتبر الاتصال/البيانات قديمة
STALE_GPS_MINUTES = 15

# ملف حفظ حالة المركبات
STATE_FILE = "/tmp/forklift_vehicle_state.json"


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
# أدوات الوقت
# =========================================================
def parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except Exception:
        return None


def gps_age_minutes(datetime_text):
    dt = parse_datetime(datetime_text)

    if dt is None:
        return None

    now = datetime.now(timezone.utc)

    age = (now - dt).total_seconds() / 60

    return round(max(age, 0), 1)


def minutes_since(datetime_text):
    dt = parse_datetime(datetime_text)

    if dt is None:
        return None

    now = datetime.now(timezone.utc)

    value = (now - dt).total_seconds() / 60

    return round(max(value, 0), 1)


def format_duration(minutes):
    if minutes is None:
        return "غير معروف"

    if minutes < 1:
        return "أقل من دقيقة"

    if minutes < 60:
        return f"{int(minutes)} دقيقة"

    hours = int(minutes // 60)
    remaining = int(minutes % 60)

    if remaining == 0:
        return f"{hours} ساعة"

    return f"{hours} ساعة و {remaining} دقيقة"


# =========================================================
# حساب المسافة بين نقطتين GPS
# =========================================================
def distance_meters(lat1, lon1, lat2, lon2):
    try:
        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)
    except (TypeError, ValueError):
        return None

    earth_radius = 6371000

    p1 = radians(lat1)
    p2 = radians(lat2)

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return earth_radius * c


# =========================================================
# تحميل / حفظ ذاكرة الحركة
# =========================================================
def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(
                STATE_FILE,
                "r",
                encoding="utf-8"
            ) as file:
                data = json.load(file)

                if isinstance(data, dict):
                    return data
    except Exception:
        pass

    return {}


def save_state(state):
    try:
        with open(
            STATE_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                state,
                file,
                ensure_ascii=False,
                indent=2
            )
    except Exception as error:
        print(
            "State save error:",
            error
        )


# =========================================================
# TrustTrack
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
# أقرب موقع معروف
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

        if distance is None:
            continue

        if (
            nearest_distance is None
            or distance < nearest_distance
        ):
            nearest_distance = distance
            nearest_name = location["name"]

    return nearest_name, nearest_distance


# =========================================================
# البحث عن Ignition إذا ظهر مستقبلاً في البيانات
# =========================================================
def detect_ignition(vehicle, coord):
    possible_values = [
        coord.get("ignition"),
        coord.get("rawIgnitionStatus"),
        coord.get("ignition_status"),
        vehicle.get("ignition"),
        vehicle.get("rawIgnitionStatus"),
        vehicle.get("ignition_status"),
    ]

    for value in possible_values:
        if value is None:
            continue

        text = str(value).strip().lower()

        if text in [
            "on",
            "running",
            "true",
            "1",
            "ignition_on",
        ]:
            return "on"

        if text in [
            "off",
            "false",
            "0",
            "ignition_off",
        ]:
            return "off"

    return "unknown"


# =========================================================
# تحليل الحركة باستخدام ذاكرة GPS
# =========================================================
def analyze_vehicle(vehicle, coord, state):
    name = str(
        vehicle.get("name")
        or vehicle.get("id")
        or "unknown"
    )

    lat = coord.get("latitude")
    lon = coord.get("longitude")
    gps_datetime = coord.get("datetime")

    age = gps_age_minutes(
        gps_datetime
    )

    ignition = detect_ignition(
        vehicle,
        coord
    )

    old = state.get(name, {})

    previous_lat = old.get("latitude")
    previous_lon = old.get("longitude")
    previous_gps_datetime = old.get(
        "gps_datetime"
    )

    last_movement = old.get(
        "last_movement"
    )

    movement_distance = 0
    new_gps_point = False
    real_movement = False

    # -----------------------------------------
    # هل وصلت نقطة GPS جديدة؟
    # -----------------------------------------
    if (
        gps_datetime
        and gps_datetime != previous_gps_datetime
    ):
        new_gps_point = True

    # -----------------------------------------
    # مقارنة الموقع السابق بالموقع الحالي
    # -----------------------------------------
    if (
        new_gps_point
        and lat is not None
        and lon is not None
        and previous_lat is not None
        and previous_lon is not None
    ):
        distance = distance_meters(
            previous_lat,
            previous_lon,
            lat,
            lon,
        )

        if distance is not None:
            movement_distance = round(
                distance,
                1
            )

            if (
                distance
                >= MOVEMENT_DISTANCE_METERS
            ):
                real_movement = True

    # -----------------------------------------
    # أول تشغيل للنظام
    # -----------------------------------------
    if (
        previous_lat is None
        or previous_lon is None
    ):
        try:
            speed = float(
                coord.get("speed") or 0
            )
        except Exception:
            speed = 0

        # في أول قراءة فقط:
        # سرعة واضحة + GPS حديث = مؤشر حركة أولي
        if (
            age is not None
            and age <= 5
            and speed >= 5
        ):
            real_movement = True

    # -----------------------------------------
    # إذا تحرك فعلياً نسجل وقت الحركة
    # -----------------------------------------
    if real_movement:
        last_movement = (
            gps_datetime
            or datetime.now(
                timezone.utc
            ).isoformat()
        )

    # -----------------------------------------
    # إذا لا يوجد تاريخ حركة بعد
    # نستخدم وقت أول نقطة معروفة
    # -----------------------------------------
    if not last_movement:
        last_movement = (
            old.get("first_seen")
            or gps_datetime
            or datetime.now(
                timezone.utc
            ).isoformat()
        )

    first_seen = old.get(
        "first_seen"
    )

    if not first_seen:
        first_seen = (
            gps_datetime
            or datetime.now(
                timezone.utc
            ).isoformat()
        )

    stopped_minutes = minutes_since(
        last_movement
    )

    # -----------------------------------------
    # تحديد الحالة
    # -----------------------------------------

    # 1 - البيانات قديمة
    if (
        age is None
        or age > STALE_GPS_MINUTES
    ):
        status_code = "stale"
        status_text = "بيانات GPS قديمة"

    # 2 - لدينا حركة GPS حقيقية
    elif real_movement:
        status_code = "moving"
        status_text = "متحرك الآن"

    # 3 - Ignition OFF مؤكد
    elif ignition == "off":
        status_code = "engine_off"
        status_text = "متوقف - المحرك مطفأ"

    # 4 - ثابت أكثر من 5 دقائق
    elif (
        stopped_minutes is not None
        and stopped_minutes
        >= STOP_AFTER_MINUTES
    ):
        if ignition == "on":
            status_code = "idle"
            status_text = (
                "متوقف - المحرك يعمل"
            )
        else:
            status_code = "stopped"
            status_text = (
                "متوقف - المحرك غير مؤكد"
            )

    # 5 - داخل فترة التأكد
    else:
        status_code = "checking"
        status_text = "جاري التحقق من الحركة"

    # -----------------------------------------
    # تحديث ذاكرة المركبة
    # -----------------------------------------
    state[name] = {
        "latitude": lat,
        "longitude": lon,
        "gps_datetime": gps_datetime,
        "last_movement": last_movement,
        "first_seen": first_seen,
        "last_status": status_code,
        "ignition": ignition,
    }

    return {
        "movement_status": status_code,
        "movement_text": status_text,
        "ignition": ignition,
        "last_movement": last_movement,
        "stopped_minutes": stopped_minutes,
        "stopped_duration": format_duration(
            stopped_minutes
        ),
        "movement_distance": movement_distance,
        "new_gps_point": new_gps_point,
        "gps_age_minutes": age,
    }


# =========================================================
# تجهيز بيانات المركبات
# =========================================================
def prepare_vehicle_data():
    data = get_vehicles()

    state = load_state()

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

        lat = coord.get("latitude")
        lon = coord.get("longitude")
        speed = coord.get("speed")
        dt = coord.get("datetime")

        location_name, distance = (
            find_known_location(
                lat,
                lon,
            )
        )

        known_location = False

        if (
            location_name is not None
            and distance is not None
        ):
            for location in KNOWN_LOCATIONS:
                if (
                    location["name"]
                    == location_name
                    and distance
                    <= location["radius"]
                ):
                    known_location = True
                    break

        analysis = analyze_vehicle(
            vehicle,
            coord,
            state,
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
                    analysis[
                        "gps_age_minutes"
                    ],

                "movement_status":
                    analysis[
                        "movement_status"
                    ],

                "movement_text":
                    analysis[
                        "movement_text"
                    ],

                "ignition":
                    analysis[
                        "ignition"
                    ],

                "last_movement":
                    analysis[
                        "last_movement"
                    ],

                "stopped_minutes":
                    analysis[
                        "stopped_minutes"
                    ],

                "stopped_duration":
                    analysis[
                        "stopped_duration"
                    ],

                "movement_distance":
                    analysis[
                        "movement_distance"
                    ],

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

    save_state(state)

    return vehicles


# =========================================================
# API الرئيسي
# =========================================================
@app.route("/")
def home():
    try:
        vehicles = prepare_vehicle_data()

        return jsonify(
            {
                "status":
                    "Forklift AI Agent is running",

                "logic":
                    "GPS + last movement + ignition",

                "stop_after_minutes":
                    STOP_AFTER_MINUTES,

                "movement_threshold_meters":
                    MOVEMENT_DISTANCE_METERS,

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
                    "status": "error",
                    "message": str(error),
                }
            ),
            500,
        )


# =========================================================
# Health
# =========================================================
@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok"
        }
    )


# =========================================================
# Objects API Test
# =========================================================
@app.route("/test-objects")
def test_objects():
    try:
        data = get_objects()

        return jsonify(
            {
                "status": "ok",
                "source":
                    "TrustTrack Objects API",
                "data": data,
            }
        )

    except Exception as error:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(error),
                }
            ),
            500,
        )


# =========================================================
# عرض ذاكرة الوكيل للاختبار
# =========================================================
@app.route("/movement-state")
def movement_state():
    return jsonify(
        {
            "status": "ok",
            "settings": {
                "movement_distance_meters":
                    MOVEMENT_DISTANCE_METERS,

                "stop_after_minutes":
                    STOP_AFTER_MINUTES,

                "stale_gps_minutes":
                    STALE_GPS_MINUTES,
            },
            "vehicles": load_state(),
        }
    )


# =========================================================
# Dashboard
# =========================================================
@app.route("/dashboard")
def dashboard():
    try:
        vehicles = prepare_vehicle_data()

        html = """
<!DOCTYPE html>

<html lang="ar" dir="rtl">

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width, initial-scale=1.0">

<meta
http-equiv="refresh"
content="30">

<title>
مركز متابعة السائقين
</title>

<style>

body {
    margin: 0;
    font-family: Arial, Tahoma, sans-serif;
    background: #f1f5f9;
    color: #0f172a;
}

.header {
    background: #14213d;
    color: white;
    padding: 28px 6%;
}

.header h1 {
    margin: 0 0 8px 0;
}

.header p {
    margin: 0;
    opacity: 0.85;
}

.summary {
    margin: 25px 6%;
    background: white;
    padding: 18px 22px;
    border-radius: 18px;
}

.grid {
    margin: 0 6% 40px 6%;
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(360px, 1fr));
    gap: 20px;
}

.card {
    background: white;
    border-radius: 18px;
    padding: 22px;
    border-top: 5px solid #2563eb;
}

.name {
    font-size: 28px;
    font-weight: bold;
    margin-bottom: 15px;
}

.badge {
    display: inline-block;
    padding: 10px 16px;
    border-radius: 30px;
    font-weight: bold;
    margin-bottom: 16px;
}

.moving {
    background: #dcfce7;
    color: #047857;
}

.idle {
    background: #fef3c7;
    color: #92400e;
}

.engine_off {
    background: #dbeafe;
    color: #1d4ed8;
}

.stopped {
    background: #e2e8f0;
    color: #334155;
}

.checking {
    background: #ede9fe;
    color: #6d28d9;
}

.stale {
    background: #ffedd5;
    color: #c2410c;
}

.row {
    display: flex;
    justify-content: space-between;
    gap: 20px;
    border-bottom: 1px solid #e2e8f0;
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

.footer-note {
    margin: 0 6% 30px 6%;
    color: #64748b;
    font-size: 14px;
}

</style>

</head>

<body>

<div class="header">

<h1>
مركز متابعة السائقين
</h1>

<p>
Forklift AI Agent —
تحليل GPS والحركة والتوقف
</p>

</div>


<div class="summary">

عدد المركبات:
<strong>
{{ vehicles|length }}
</strong>

&nbsp; | &nbsp;

التوقف يعتمد بعد
<strong>5 دقائق</strong>
من عدم وجود حركة فعلية.

&nbsp; | &nbsp;

تحديث كل
<strong>30 ثانية</strong>

</div>


<div class="grid">

{% for v in vehicles %}

<div class="card">

<div class="name">
{{ v.name }}
</div>


<div class="badge {{ v.movement_status }}">

{% if v.movement_status == "moving" %}
🟢
{% elif v.movement_status == "idle" %}
🟡
{% elif v.movement_status == "engine_off" %}
🔵
{% elif v.movement_status == "stopped" %}
⚪
{% elif v.movement_status == "stale" %}
🟠
{% else %}
🟣
{% endif %}

{{ v.movement_text }}

</div>


<div class="row">

<span class="label">
آخر سرعة مسجلة
</span>

<span class="value">

{{ v.speed if v.speed is not none else "غير متوفرة" }}

{% if v.speed is not none %}
كم/س
{% endif %}

</span>

</div>


<div class="row">

<span class="label">
آخر حركة مؤكدة
</span>

<span class="value">
{{ v.last_movement or "غير معروفة" }}
</span>

</div>


<div class="row">

<span class="label">
مدة عدم الحركة
</span>

<span class="value">
{{ v.stopped_duration }}
</span>

</div>


<div class="row">

<span class="label">
المسافة منذ القراءة السابقة
</span>

<span class="value">
{{ v.movement_distance }} متر
</span>

</div>


<div class="row">

<span class="label">
حالة المحرك
</span>

<span class="value">

{% if v.ignition == "on" %}

يعمل

{% elif v.ignition == "off" %}

مطفأ

{% else %}

غير مؤكدة

{% endif %}

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

{{ v.distance_meters }} متر

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

{{ v.gps_age_minutes }} دقيقة

{% else %}

غير معروف

{% endif %}

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


<div class="footer-note">

🟢 متحرك —
🟡 متوقف والمحرك يعمل —
🔵 المحرك مطفأ —
⚪ متوقف والمحرك غير مؤكد —
🟠 بيانات GPS قديمة

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
