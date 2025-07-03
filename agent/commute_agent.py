# ✅ commute_agent.py (with fixed 'too far' logic)
import datetime
import asyncio
from .subway import get_subway_arrivals
from .nj_transit import get_nj_transit_trains
from .geo import is_near_penn_station
from utils.location_store import load_location
from utils.sms import send_alert_whatsapp

def is_too_far_from_penn(lat, lon, threshold_meters=2000):
    return not is_near_penn_station(lat, lon, threshold_meters)

def format_commute_summary(subway_arrivals, njt_status, recommendation):
    msg_lines = ["🚇 *Next Subway Trains (59th & Lex)*"]
    if subway_arrivals:
        for train in subway_arrivals:
            msg_lines.append(f"• {train}")
    else:
        msg_lines.append("• No subway trains found.")

    msg_lines.append("\n🚉 *Next NJ Transit Trains to Newark Penn*")
    
    for train in njt_status.get("next_trains", []):
        msg_lines.append(f"• {train['time']} {train['destination']} {train['track']} ({train['status']})")

    msg_lines.append("")
    msg_lines.append(f"🧠 *Recommendation:* {recommendation}")
    return "\n".join(msg_lines)

async def trigger_commute_agent(location="unknown"):
    latest_location = load_location()
    print("📡 latest_location =", latest_location)
    subway_arrivals = get_subway_arrivals()
    njt_status = await get_nj_transit_trains()

    recommendation = "Proceed to NY Penn as usual."
    distance_check = "Unknown"
    if latest_location:
        lat = latest_location.get("lat")
        lon = latest_location.get("lon")
        print(f"🧭 Location received: lat={lat}, lon={lon}")

        if is_too_far_from_penn(lat, lon):
            recommendation = "📍 You are too far from Penn Station. Geo-monitoring will be skipped for 10 minutes."
            distance_check = "too_far"
        else:
            if is_near_penn_station(lat, lon):
                if njt_status.get("delayed"):
                    recommendation = "⚠️ NJ Transit is delayed. Take PATH from 33rd St."
                else:
                    recommendation = "✅ NJ Transit appears on time. Proceed to Penn."

    message = format_commute_summary(subway_arrivals, njt_status, recommendation)
    send_alert_whatsapp(message)

    return {
        "status": "commute monitoring started",
        "timestamp": datetime.datetime.now().isoformat(),
        "subway": subway_arrivals,
        "nj_transit": njt_status,
        "recommendation": recommendation,
        "location": latest_location or "not provided",
        "distance_check": distance_check
    }

async def start_background_monitoring():
    for _ in range(10):
        await asyncio.sleep(60)
        latest_location = load_location()
        if not latest_location:
            continue

        lat = latest_location.get("lat")
        lon = latest_location.get("lon")

        if is_near_penn_station(lat, lon):
            njt = get_nj_transit_trains()
            if njt.get("delayed"):
                summary = format_commute_summary([], njt, "⚠️ NJ Transit is delayed. Take PATH from 33rd St.")
                send_alert_whatsapp(summary)
                print("✅ WhatsApp message sent, stopping loop.")
                break
