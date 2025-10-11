
# agent/auto_trigger.py

import os
import asyncio
import logging
from datetime import datetime, time
from dotenv import load_dotenv
from agent.clients.bus_client import NJTransitBusAPIClient
from agent.clients.rail_client import NJTransitRailAPIClient
from agent.commute_agent import trigger_commute_agent

load_dotenv()

logger = logging.getLogger(__name__)

NJT_USERNAME = os.getenv("NJT_USERNAME")
NJT_PASSWORD = os.getenv("NJT_PASSWORD")
NJT_BUS_BASE_URL = os.getenv("NJT_BUS_BASE_URL")
NJT_RAIL_BASE_URL = os.getenv("NJT_RAIL_BASE_URL")

bus_client = NJTransitBusAPIClient(NJT_USERNAME, NJT_PASSWORD, NJT_BUS_BASE_URL)
rail_client = NJTransitRailAPIClient(NJT_USERNAME, NJT_PASSWORD, NJT_RAIL_BASE_URL)

# State tracking
triggered_windows = set()  # Track which time windows have been triggered
notification_cooldown_minutes = 15  # Don't spam notifications


def should_trigger_morning_alert() -> tuple[bool, str]:
    """
    Check if we should trigger a morning bus alert based on:
    1. Time window (5:45-6:05 AM or 6:05-6:30 AM)
    2. Bus is approaching/arriving soon
    3. Haven't notified in this window yet

    Returns: (should_trigger: bool, window_id: str)
    """
    now = datetime.now()
    current_time = now.time()

    # Define two time windows
    window1_start = time(5, 45)  # 5:45 AM
    window1_end = time(6, 5)     # 6:05 AM
    window2_start = time(6, 5)   # 6:05 AM
    window2_end = time(6, 30)    # 6:30 AM

    # Check if we've already triggered in this window
    global triggered_windows

    # Determine which window we're in
    window_id = None
    if window1_start <= current_time < window1_end:
        window_id = "window1_5:45-6:05"
    elif window2_start <= current_time <= window2_end:
        window_id = "window2_6:05-6:30"
    else:
        # Outside all windows - reset for next day
        if current_time > window2_end:
            triggered_windows.clear()
        return False, None

    if window_id in triggered_windows:
        logger.debug(f"Already triggered in {window_id}")
        return False, window_id

    return True, window_id


def check_bus_approaching(is_fallback_time: bool = False) -> dict:
    """
    Check if confirmed buses (not EMPTY) are approaching/active.
    Returns dict with status and bus info.
    Only triggers on actual buses with valid vehicle IDs.

    Args:
        is_fallback_time: If True (at 5:55 AM or 6:20 AM), send notification even if bus is EMPTY
    """
    try:
        # Get scheduled buses
        scheduled = bus_client.get_bus_schedule_to_nyc(limit=5)

        # Get live bus positions
        live_trips = bus_client.get_bus_live_trips_from_stop()

        # Filter out EMPTY buses - only keep confirmed vehicles
        confirmed_buses = []
        all_live_trips = live_trips or []

        if all_live_trips:
            for trip in all_live_trips:
                vehicle_id = trip.get('vehicle_id', '')
                # Filter out EMPTY or missing vehicle IDs
                if vehicle_id and vehicle_id.strip() and vehicle_id.upper() != 'EMPTY':
                    confirmed_buses.append(trip)
                    logger.info(f"🚍 Confirmed bus detected: #{vehicle_id}")

        # Check if there are any buses in the next 30 minutes
        now = datetime.now()
        upcoming_buses = []

        for bus in scheduled.get("next_buses", []):
            bus_time_str = bus.get("time", "")
            try:
                # Parse bus time (format: "HH:MM AM/PM")
                bus_time = datetime.strptime(bus_time_str, "%I:%M %p").time()
                bus_datetime = now.replace(hour=bus_time.hour, minute=bus_time.minute, second=0)

                # Check if bus is within next 30 minutes
                time_until_bus = (bus_datetime - now).total_seconds() / 60

                if 0 <= time_until_bus <= 30:
                    upcoming_buses.append({
                        "time": bus_time_str,
                        "minutes_away": int(time_until_bus),
                        "status": bus.get("remarks", "On time")
                    })
            except Exception as e:
                logger.warning(f"Failed to parse bus time '{bus_time_str}': {e}")

        # CONFIRMED buses detected - trigger immediately
        if confirmed_buses:
            closest_bus = confirmed_buses[0]
            vehicle_id = closest_bus.get('vehicle_id', 'N/A')
            logger.info(f"🛰️ Confirmed live bus detected: #{vehicle_id}")
            return {
                "should_notify": True,
                "reason": "confirmed_bus_detected",
                "live_buses": confirmed_buses,
                "upcoming_buses": upcoming_buses
            }

        # FALLBACK: At 5:55 AM or 6:20 AM, send notification even if bus is EMPTY
        if is_fallback_time:
            logger.info(f"⏰ Fallback time reached - sending notification even with EMPTY buses")
            return {
                "should_notify": True,
                "reason": "fallback_time_trigger",
                "live_buses": all_live_trips,  # Include EMPTY buses
                "upcoming_buses": upcoming_buses
            }

        # Don't trigger on scheduled buses alone - wait for confirmed tracking
        logger.debug(f"Only scheduled buses found, no confirmed vehicles yet")
        return {
            "should_notify": False,
            "reason": "no_confirmed_buses",
            "upcoming_buses": upcoming_buses
        }

    except Exception as e:
        logger.error(f"❌ Error checking bus status: {e}", exc_info=True)
        return {"should_notify": False, "reason": "error", "error": str(e)}


async def morning_bus_check(auto_trigger_enabled: bool = True):
    """
    Periodic check for morning bus - runs every 5 minutes during morning hours.
    Triggers once per time window when a confirmed bus (not EMPTY) is detected.
    Windows: 5:45-6:05 AM, then 6:05-6:30 AM
    Fallback: At 5:55 AM or 6:20 AM, send notification even if bus is still EMPTY
    """
    logger.info("🔍 Running morning bus check...")

    # Check if auto-trigger is enabled
    if not auto_trigger_enabled:
        logger.debug("Auto-trigger is disabled")
        return

    should_trigger, window_id = should_trigger_morning_alert()
    if not should_trigger:
        logger.debug(f"Outside morning window or already triggered for {window_id}")
        return

    # Check if we're at fallback time (5:55 AM or 6:20 AM)
    now = datetime.now()
    current_time = now.time()
    fallback_time1 = time(5, 55)  # 5:55 AM
    fallback_time2 = time(6, 20)  # 6:20 AM

    # Consider it fallback time if within 3 minutes of the exact time
    is_fallback = False
    if window_id == "window1_5:45-6:05":
        # Check if close to 5:55 AM (between 5:53 and 5:57)
        is_fallback = time(5, 53) <= current_time <= time(5, 57)
    elif window_id == "window2_6:05-6:30":
        # Check if close to 6:20 AM (between 6:18 and 6:22)
        is_fallback = time(6, 18) <= current_time <= time(6, 22)

    if is_fallback:
        logger.info(f"⏰ Fallback time detected in {window_id}")

    bus_status = check_bus_approaching(is_fallback_time=is_fallback)

    if bus_status.get("should_notify"):
        logger.info(f"✅ Triggering alert: {bus_status.get('reason')} in {window_id}")

        # Trigger the commute agent for home zone
        try:
            await trigger_commute_agent(location="home", lat=None, lon=None)

            # Mark this window as triggered
            global triggered_windows
            triggered_windows.add(window_id)

            logger.info(f"📤 Morning commute alert sent successfully for {window_id}")
        except Exception as e:
            logger.error(f"❌ Failed to trigger commute agent: {e}", exc_info=True)
    else:
        logger.debug(f"No notification needed: {bus_status.get('reason')}")


# ============ AFTERNOON RAIL ALERT ============


def should_trigger_afternoon_alert() -> tuple[bool, str]:
    """
    Check if we should trigger an afternoon rail alert for evening commute.
    Time window: 1:30 PM - 1:50 PM
    Checks for delays from Penn Station to Newark that may affect 3:40 PM commute.

    Returns: (should_trigger: bool, window_id: str)
    """
    now = datetime.now()
    current_time = now.time()
    global triggered_windows

    # Afternoon alert window
    afternoon_start = time(13, 30)  # 1:30 PM
    afternoon_end = time(13, 50)    # 1:50 PM

    window_id = "afternoon_1:30-1:50"

    # Check if we're in the afternoon window
    if not (afternoon_start <= current_time <= afternoon_end):
        # Reset state after window ends
        if current_time > afternoon_end:
            if window_id in triggered_windows:
                triggered_windows.discard(window_id)
        return False, None

    # Check if we've already triggered in this window today
    if window_id in triggered_windows:
        logger.debug(f"Already triggered afternoon alert today")
        return False, window_id

    return True, window_id


def check_rail_delays() -> dict:
    """
    Check for rail delays from Penn Station (NY) to Newark.
    Looks for delays that may affect the 3:40 PM evening commute.
    """
    try:
        # Get station alerts from Penn Station
        station_alerts = rail_client.get_station_alerts("NY")

        # Get train schedule to check for delays
        train_schedule = rail_client.get_train_schedule("NY", limit=10)

        # Filter alerts relevant to Newark-bound trains (NEC, RARV, NJCL lines)
        relevant_keywords = [
            "DELAY", "CANCEL", "SUSPEND",
            "NEC", "RARV", "NJCL",
            "NEWARK", "FANWOOD", "WESTFIELD",
            "FROM PSNY", "FROM NY"
        ]

        relevant_alerts = []
        for alert in station_alerts:
            alert_upper = alert.upper()
            # Check if alert mentions delays AND is relevant to Newark-bound lines
            if "DELAY" in alert_upper or "CANCEL" in alert_upper or "SUSPEND" in alert_upper:
                if any(keyword in alert_upper for keyword in relevant_keywords):
                    relevant_alerts.append(alert)

        # Check if any upcoming trains are delayed
        delayed_trains = [t for t in train_schedule.get("next_trains", []) if "DELAY" in t.get("status", "").upper()]

        has_delays = len(relevant_alerts) > 0 or len(delayed_trains) > 0

        if has_delays:
            logger.info(f"🚨 Rail delays detected: {len(relevant_alerts)} alerts, {len(delayed_trains)} delayed trains")
            return {
                "should_notify": True,
                "reason": "rail_delays_detected",
                "alerts": relevant_alerts,
                "delayed_trains": delayed_trains,
                "all_trains": train_schedule.get("next_trains", [])
            }
        else:
            logger.debug("No significant rail delays detected")
            return {
                "should_notify": False,
                "reason": "no_delays",
                "alerts": [],
                "all_trains": train_schedule.get("next_trains", [])
            }

    except Exception as e:
        logger.error(f"❌ Error checking rail delays: {e}", exc_info=True)
        return {"should_notify": False, "reason": "error", "error": str(e)}


async def afternoon_rail_check(auto_trigger_enabled: bool = True):
    """
    Periodic check for afternoon rail delays - runs during 1:30-1:50 PM.
    Checks for delays from Penn Station to Newark that may affect 3:40 PM commute.
    Triggers once per day if delays are detected.
    """
    logger.info("🔍 Running afternoon rail delay check...")

    # Check if auto-trigger is enabled
    if not auto_trigger_enabled:
        logger.debug("Auto-trigger is disabled")
        return

    should_trigger, window_id = should_trigger_afternoon_alert()
    if not should_trigger:
        logger.debug(f"Outside afternoon window or already triggered for {window_id}")
        return

    rail_status = check_rail_delays()

    if rail_status.get("should_notify"):
        logger.info(f"✅ Triggering afternoon alert: {rail_status.get('reason')}")

        # Trigger the commute agent for Newark zone to get evening commute info
        try:
            await trigger_commute_agent(location="newark", lat=None, lon=None)

            # Mark this window as triggered
            global triggered_windows
            triggered_windows.add(window_id)

            logger.info(f"📤 Afternoon rail alert sent successfully")
        except Exception as e:
            logger.error(f"❌ Failed to trigger afternoon rail alert: {e}", exc_info=True)
    else:
        logger.debug(f"No afternoon notification needed: {rail_status.get('reason')}")
