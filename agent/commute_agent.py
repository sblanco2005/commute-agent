# agent/commute_agent.py

import os
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from .clients.subway import get_subway_arrivals
from agent.clients.bus_client import NJTransitBusAPIClient
from agent.clients.rail_client import NJTransitRailAPIClient
from .geo import get_location_zone
from utils.sms import send_alert_whatsapp,send_alert
from agent.clients.weather import get_weather_alerts_by_coords
from agent.geo import HOME_COORDS, OFFICE_COORDS

load_dotenv()

NJT_USERNAME = os.getenv("NJT_USERNAME")
NJT_PASSWORD = os.getenv("NJT_PASSWORD")
NJT_BUS_BASE_URL = os.getenv("NJT_BUS_BASE_URL")
NJT_RAIL_BASE_URL = os.getenv("NJT_RAIL_BASE_URL")
WEATHER_KEY = os.getenv("WEATHER_KEY")



assert NJT_USERNAME and NJT_PASSWORD and NJT_BUS_BASE_URL and NJT_RAIL_BASE_URL

bus_client = NJTransitBusAPIClient(NJT_USERNAME, NJT_PASSWORD, NJT_BUS_BASE_URL)
rail_client = NJTransitRailAPIClient(NJT_USERNAME, NJT_PASSWORD, NJT_RAIL_BASE_URL)

# Timezone configuration - NJ Transit API returns times in Eastern Time
EASTERN_TZ = ZoneInfo("America/New_York")

AUTO_HOME_FALLBACK_METERS = 10000

def format_commute_summary(subway_arrivals, njt_status, recommendation, station_alerts=None, weather=None):
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
        filtered = [a for a in station_alerts if any(k in a.upper() for k in ["NEC", "NJCL", "RARV"]) and "FROM PSNY" in a.upper()]
        if filtered:
            msg_lines.append("\n🚨 *Relevant Station Alerts*")
            msg_lines.extend(f"• {alert}" for alert in filtered)

    if weather:
        home_weather = weather.get("home", {})
        nyc_weather = weather.get("nyc", {})

        home_condition = home_weather.get("description", "Unknown").capitalize()
        home_temp = home_weather.get("temp_celsius", "N/A")
        home_alerts = home_weather.get("alerts", [])

        nyc_condition = nyc_weather.get("description", "Unknown").capitalize()
        nyc_temp = nyc_weather.get("temp_celsius", "N/A")
        nyc_alerts = nyc_weather.get("alerts", [])

        msg_lines.append(
            f"\n🌤️ *Weather (Home):* {home_condition} | {home_temp}°C" +
            (f"\n🚨 Home Alerts: " + "; ".join(home_alerts) if home_alerts else "")
        )

        msg_lines.append(
            f"\n🏙️ *Weather (NYC):* {nyc_condition} | {nyc_temp}°C" +
            (f"\n🚨 NYC Alerts: " + "; ".join(nyc_alerts) if nyc_alerts else "")
        )

    full_message = "\n".join(msg_lines).strip()
    MAX_LEN = 1590
    return full_message[:MAX_LEN] + ("\n...[truncated]" if len(full_message) > MAX_LEN else "")

def format_home_message(status, recommendation, weather=None):
    msg = ["🚌 *113X Bus Departures to Port Authority from Fanwood*"]

    for bus in status.get("next_buses", []):
        time = bus.get("time", "N/A")
        header = (bus.get("header", "") or "")[:40].strip()
        route = bus.get("route", "N/A")
        gate = f"(Gate {bus.get('lanegate', '')})" if bus.get("lanegate") else ""
        remarks = bus.get("remarks", "On time").strip()
        msg.append(f"• {time} → {header} {gate}\n  • Route: {route} | Status: {remarks}")

    live_trips = status.get("live_trips", [])
    if live_trips:
        msg.append("\n🛰️ *Live Vehicles (Real-Time Tracking)*")
        for trip in live_trips:
            vehicle = trip.get('vehicle_id', 'N/A')
            header = trip.get('header', 'Unknown')
            departure = trip.get('departure_time', 'N/A')
            load = trip.get('passenger_load', '')

            # Show real-time arrival if available
            if trip.get('has_realtime'):
                realtime_str = trip.get('realtime_arrival', '')  # Format: "min:sec" from GPS
                destination = trip.get('stop_status', 'Unknown')

                # Parse GPS-based ETA (format: "7:32" = 7 minutes 32 seconds)
                minutes_away = "N/A"
                try:
                    if ':' in realtime_str:
                        parts = realtime_str.split(':')
                        total_minutes = int(parts[0])
                        seconds = int(parts[1]) if len(parts) > 1 else 0

                        if total_minutes < 1:
                            minutes_away = "Less than 1 minute"
                        elif total_minutes == 1:
                            minutes_away = "1 minute"
                        else:
                            minutes_away = f"{total_minutes} minutes"
                    else:
                        minutes_away = realtime_str
                except Exception as e:
                    minutes_away = realtime_str

                msg.append(f"• Bus #{vehicle} → {destination}")
                msg.append(f"  🎯 Arriving in {minutes_away}")
                if load:
                    msg.append(f"  👥 Load: {load}")
            else:
                # Fallback to old format if no real-time data
                trip_status = trip.get('status', 'Unknown')
                msg.append(f"• Bus #{vehicle} → {header} at {departure} ({trip_status})")
                if load:
                    msg.append(f"  👥 Load: {load}")
    if weather:
        home_weather = weather.get("home", {})
        nyc_weather = weather.get("nyc", {})

        home_condition = home_weather.get("description", "Unknown").capitalize()
        home_temp = home_weather.get("temp_celsius", "N/A")
        home_alerts = home_weather.get("alerts", [])

        nyc_condition = nyc_weather.get("description", "Unknown").capitalize()
        nyc_temp = nyc_weather.get("temp_celsius", "N/A")
        nyc_alerts = nyc_weather.get("alerts", [])

        msg.append(
            f"\n🌤️ *Weather (Home):* {home_condition} | {home_temp}°C" +
            (f"\n🚨 Home Alerts: " + "; ".join(home_alerts) if home_alerts else "")
        )

        msg.append(
            f"\n🏙️ *Weather (NYC):* {nyc_condition} | {nyc_temp}°C" +
            (f"\n🚨 NYC Alerts: " + "; ".join(nyc_alerts) if nyc_alerts else "")
        )


    return "\n".join(msg)

def format_newark_message(njt_status, recommendation,weather=None):
    msg = ["🚉 *Trains from Newark to Fanwood*"]
    for train in njt_status.get("next_trains", [])[:3]:
        msg.append(f"• {train['time']} → {train['destination']} ({train['status']})")
    
    if weather:
        home_weather = weather.get("home", {})
        nyc_weather = weather.get("nyc", {})

        home_condition = home_weather.get("description", "Unknown").capitalize()
        home_temp = home_weather.get("temp_celsius", "N/A")
        home_alerts = home_weather.get("alerts", [])

        nyc_condition = nyc_weather.get("description", "Unknown").capitalize()
        nyc_temp = nyc_weather.get("temp_celsius", "N/A")
        nyc_alerts = nyc_weather.get("alerts", [])

        msg.append(
            f"\n🌤️ *Weather (Home):* {home_condition} | {home_temp}°C" +
            (f"\n🚨 Home Alerts: " + "; ".join(home_alerts) if home_alerts else "")
        )

        msg.append(
            f"\n🏙️ *Weather (NYC):* {nyc_condition} | {nyc_temp}°C" +
            (f"\n🚨 NYC Alerts: " + "; ".join(nyc_alerts) if nyc_alerts else "")
        )

    return "\n".join(msg)

async def trigger_commute_agent(location=None, lat=None, lon=None):
    if location in {"", None, "triggered_from_phone", "unknown"}:
        if lat is None or lon is None:
            return {"error": "lat/lon required"}
        zone = get_location_zone(lat, lon)
        if zone == "unknown":
            zone = "home"
    else:
        zone = location.lower()
    #weather_home = get_weather_alerts_by_coords(WEATHER_KEY, *HOME_COORDS)
    #weather_nyc = get_weather_alerts_by_coords(WEATHER_KEY, *OFFICE_COORDS)

    
    # New - async
    weather_home, weather_nyc = await asyncio.gather(
    get_weather_alerts_by_coords(WEATHER_KEY, *HOME_COORDS),
    get_weather_alerts_by_coords(WEATHER_KEY, *OFFICE_COORDS),
    )
    

    weather = None
    recommendation = "⚠️ Unable to determine commute recommendation."

    if weather_home.get("description", "").lower() in {"rain", "thunderstorm"}:
        recommendation = "⚠️ Bad weather expected in Fanwood. Consider leaving early."
    elif weather_nyc.get("description", "").lower() in {"rain", "thunderstorm"}:
        recommendation = "⚠️ Bad weather expected in NYC. Consider taking precautions."

    weather = {
        "home": weather_home,
        "nyc": weather_nyc,
    }
    print(weather)

    if zone == "home":
        if not recommendation.startswith("⚠️"):
            recommendation = "🚌 Checking 113X bus from Fanwood..."
        scheduled = bus_client.get_bus_schedule_to_nyc()
        live = bus_client.get_bus_live_trips_from_stop()
        scheduled["live_trips"] = live
        message = format_home_message(scheduled, recommendation, weather)

    elif zone == "nyc":
        subway_arrivals = get_subway_arrivals()
        njt_status = rail_client.get_train_schedule("NY")
        station_alerts = rail_client.get_station_alerts("NY")
        if not recommendation.startswith("⚠️"):
            recommendation = "Proceed to Penn as usual." if not njt_status.get("delayed") else "⚠️ Delay detected. Take PATH."
        message = format_commute_summary(subway_arrivals, njt_status, recommendation, station_alerts, weather)

    elif zone == "newark":
        njt_status = rail_client.get_train_schedule("NP")
        recommendation = "🚉 Checking train schedule from Newark to Fanwood..."
        message = format_newark_message(njt_status, recommendation,weather)

    else:
        message = "📍 Location not recognized. Cannot trigger agent."

    if lat and lon:
        message += f"\n📍 *Coordinates:* {lat:.5f}, {lon:.5f}"


    send_alert(message, channels=("telegram",))  # or ("whatsapp", "telegram")
    

    return {
        "status": "ok",
        "zone": zone,
        "recommendation": recommendation,
        "message_sent": message
    }