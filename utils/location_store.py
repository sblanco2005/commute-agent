import json
import os

LOCATION_FILE = "location_store.json"

def save_location(lat, lon, timestamp):
    with open(LOCATION_FILE, "w") as f:
        json.dump({"lat": lat, "lon": lon, "timestamp": timestamp}, f)

def load_location():
    if os.path.exists(LOCATION_FILE):
        with open(LOCATION_FILE, "r") as f:
            return json.load(f)
    return {}