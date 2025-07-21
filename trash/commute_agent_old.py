# ✅ commute_agent.py
import os
from dotenv import load_dotenv
from ..agent.clients.subway import get_subway_arrivals
from agent.clients.bus_client import NJTransitBusAPIClient
from agent.clients.rail_client import NJTransitRailAPIClient
from ..agent.geo import get_location_zone  
from utils.sms import send_alert_whatsapp
from agent.clients.weather import get_weather_alerts

# Example: use Bloomberg location for weather (NYC)
WEATHER_LAT_LON = {"home": (40.6414, -74.3869), "nyc": (40.7580, -73.9787)}

# Load environment variables before using os.getenv
load_dotenv()

# Validate critical environment variables
NJT_USERNAME = os.getenv("NJT_USERNAME")
NJT_PASSWORD = os.getenv("NJT_PASSWORD")
NJT_BUS_BASE_URL = os.getenv("NJT_BUS_BASE_URL")
NJT_RAIL_BASE_URL = os.getenv("NJT_RAIL_BASE_URL")
NJT_BASE_URL = os.getenv("NJT_BASE_URL")
WEATHER_KEY = os.getenv("WEATHER_KEY")

assert NJT_USERNAME, "Missing NJT_USERNAME in .env"
assert NJT_PASSWORD, "Missing NJT_PASSWORD in .env"
assert NJT_BUS_BASE_URL, "Missing NJT_BUS_BASE_URL in .env"
assert NJT_RAIL_BASE_URL, "Missing NJT_RAIL_BASE_URL in .env"

# Initialize NJT API clients
bus_client = NJTransitBusAPIClient(
    username=NJT_USERNAME,
    password=NJT_PASSWORD,
    base_url=NJT_BUS_BASE_URL
)

rail_client = NJTransitRailAPIClient(
    username=NJT_USERNAME,
    password=NJT_PASSWORD,
    base_url=NJT_RAIL_BASE_URL
)


def format_commute_summary(subway_arrivals, njt_status, recommendation, station_alerts=None):
    msg_lines = ["🚇 *Next Subway Trains (59th & Lex)*"]
    
    if subway_arrivals:
        for train in subway_arrivals:
            msg_lines.append(f"• {train}")
    else:
        msg_lines.append("• No subway trains found.")

    msg_lines.append("\n🚉 *Next NJ Transit Trains to Newark Penn*")
    for train in njt_status.get("next_trains", []):
        track = train["track"]
        track_text = f"Track {track}" if track != "?" else "Track unknown"
        msg_lines.append(f"• {train['time']} → {train['destination']} ({track_text}, {train['status']})")
    
    if station_alerts:
        relevant_alerts = [
            alert for alert in station_alerts
            if (
                any(keyword in alert.upper() for keyword in ["NEC", "NJCL", "RARV"])
                and "FROM PSNY" in alert.upper()
            )
        ]
        if relevant_alerts:
            msg_lines.append("\n🚨 *Relevant Station Alerts*")
            for alert in relevant_alerts:
                msg_lines.append(f"• {alert}")

    msg_lines.append("")
    
    full_message = "\n".join(msg_lines).strip()

    # 🔒 Hard limit at 1590 to stay under Twilio's 1600-char limit
    TRUNCATION_NOTICE = "\n...[truncated]"
    MAX_LEN = 1600 - len(TRUNCATION_NOTICE)-10

    if len(full_message) > MAX_LEN:
        full_message = full_message[:MAX_LEN] + TRUNCATION_NOTICE


    print(f"📏 WhatsApp message length: {len(full_message)}")
    return full_message

def format_home_message(status: dict, recommendation: str) -> str:
    """
    Format message with scheduled buses and real-time vehicle IDs from Fanwood to NYC.
    """
    msg = ["🚌 *113X Bus Departures to Port Authority from Fanwood*"]

    # ── Scheduled buses ───────────────────────
    scheduled_buses = status.get("next_buses", [])
    if scheduled_buses:
        for bus in scheduled_buses:
            time = bus.get("time", "N/A")
            header = bus.get("header", "").strip()
            route = bus.get("route", "N/A")
            lanegate = bus.get("lanegate", "")
            remarks = bus.get("remarks", "").strip() or "On time"

            if len(header) > 40:
                header = header[:37].rstrip() + "…"

            gate_text = f"(Gate {lanegate})" if lanegate else ""
            msg.append(f"• {time} → {header} {gate_text}\n  • Route: {route} | Status: {remarks}")
    else:
        msg.append("• No upcoming buses found.")

    # ── Live buses ────────────────────────────
    live_trips = status.get("live_trips", [])
    if live_trips:
        msg.append("\n🛰️ *Live Vehicles (Detected by NJT)*")
        for trip in live_trips:
            bus_id = trip.get("vehicle_id", "Unknown")
            dep_time = trip.get("departure_time", "N/A")
            header = trip.get("header", "").strip()
            trip_status = trip.get("status", "N/A")
            msg.append(f"• Bus #{bus_id} → {header} at {dep_time} ({trip_status})")
    else:
        msg.append("\n• No live bus trips detected by NJT.")

    # ── Final recommendation ──────────────────
    msg.append(f"\n🧠 *Recommendation:* {recommendation}")

    return "\n".join(msg).strip()

def format_newark_message(njt_status, recommendation):
    msg = ["🚉 *Trains from Newark to Fanwood*"]
    trains = njt_status.get("next_trains", [])
    if trains:
        for train in trains[:3]:
            msg.append(f"• {train['time']} → {train['destination']} ({train['status']})")
    else:
        msg.append("• No trains found from Newark.")

    msg.append("")
    return "\n".join(msg)


AUTO_HOME_FALLBACK_METERS = 10000        # if no zone match within this radius

async def trigger_commute_agent(
    location: str | None = "unknown",
    lat: float | None = None,
    lon: float | None = None,
):
    """
    • If `location` is a real zone name ("nyc", "home") → use it.
    • Else we MUST have lat/lon from the phone; we derive the zone.
    • If no zone match within 300 m, we default to 'home'.
    """

    # 1️⃣  Treat these tokens as "no manual override"
    NO_OVERRIDE = {"unknown", "", None, "triggered_from_phone"}

    # ── manual override branch ──────────────────────────────────
    if location not in NO_OVERRIDE:
        zone = location.lower()
        print("📍 Manual override zone:", zone)

    # ── automatic (GPS) branch ─────────────────────────────────
    else:
        # ensure the phone sent coordinates
        if lat is None or lon is None:
            return {"error": "lat/lon missing from request body"}

        print(f"📱 GPS from phone → lat={lat}, lon={lon}")

        zone = get_location_zone(lat, lon)      # your own helper
        print("📍 Auto-detected zone:", zone)

        # If we're farther than threshold from any known zone → default to 'home'
        if zone == "unknown":
            print(
                f"📏 >{AUTO_HOME_FALLBACK_METERS} m from any zone, "
                "defaulting to 'home'"
            )
            zone = "home"
   
    subway_arrivals = []
    njt_status = {}
    station_alerts = []
    recommendation = "⚠️ Unable to determine your location context."

    if zone == "home":
        recommendation = "🚌 Checking 113X bus from Fanwood..."
        njt_status = bus_client.get_bus_schedule_to_nyc()
        scheduled = bus_client.get_bus_schedule_to_nyc()
        live = bus_client.get_bus_live_trips_from_stop()
        scheduled["live_trips"] = live
        njt_status = scheduled
        message = format_home_message(njt_status, recommendation)

    elif zone == "nyc":
        subway_arrivals = get_subway_arrivals()
        njt_status = rail_client.get_train_schedule("NY")
        station_alerts = rail_client.get_station_alerts(station_code="NY")
        recommendation = "Proceed to Penn as usual." if not njt_status.get("delayed") else "⚠️ Delay detected. Take PATH."
        message = format_commute_summary(subway_arrivals, njt_status, recommendation, station_alerts)

    elif zone == "newark":
        njt_status = rail_client.get_train_schedule("NP")
        station_alerts = rail_client.get_station_alerts(station_code="NP")
        recommendation = "🚉 Checking train schedule from Newark to Fanwood..."
        message = format_newark_message(njt_status, recommendation)

    else:
        message = "📍 Location not recognized. Cannot trigger agent."

    # Truncate if too long for WhatsApp/SMS
    if len(message) > 1600:
        message = message[:1590] + "\n...[truncated]"
# 📍 Append location if available
    if lat is not None and lon is not None:
        message += f"\n📍 *Coordinates:* {lat:.5f}, {lon:.5f}"


    send_alert_whatsapp(message)

    return {
        "status": "ok",
        "zone": zone,
        "recommendation": recommendation,
        "message_sent": message
    }