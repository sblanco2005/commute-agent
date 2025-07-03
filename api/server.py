# ✅ api/server.py (FastAPI endpoint)
from fastapi import FastAPI
from agent.commute_agent import trigger_commute_agent, start_background_monitoring
from agent.geo import is_near_penn_station
import asyncio

app = FastAPI()

from utils.location_store import save_location, load_location

@app.post("/update_location")
async def update_location(payload: dict):
    save_location(payload["lat"], payload["lon"], payload["timestamp"])
    print("📍 Location updated:", payload)
    return {"status": "Location updated"}

@app.post("/trigger")
async def trigger_commute():
    result = await trigger_commute_agent(location="triggered_from_phone")

    latest_location = load_location()
    # Check distance before starting background loop
    if latest_location:
        lat = latest_location.get("lat")
        lon = latest_location.get("lon")
        if not is_near_penn_station(lat, lon, threshold_meters=300):
            result["recommendation"] = "📍 You are too far from Penn Station to start monitoring."
            result["monitoring_started"] = False
            return result

    # Close enough, start monitor loop
    asyncio.create_task(start_background_monitoring())
    result["monitoring_started"] = True
    return result