import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

API_KEY = os.environ.get("TRUSTTRACK_API_KEY")
BASE_URL = "https://api.fm-track.com"


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


@app.route("/")
def home():
    try:
        data = get_vehicles()

        vehicles = []

        for vehicle in data.get("results", []):
            coord = vehicle.get("last_coordinate") or {}

            vehicles.append({
                "name": vehicle.get("name"),
                "speed": coord.get("speed"),
                "latitude": coord.get("latitude"),
                "longitude": coord.get("longitude"),
                "datetime": coord.get("datetime")
            })

        return jsonify({
            "status": "Forklift AI Agent is running",
            "vehicles": vehicles
        })

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})
