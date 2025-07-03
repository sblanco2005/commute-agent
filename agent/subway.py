import requests
import datetime
import math
from google.transit import gtfs_realtime_pb2
from zoneinfo import ZoneInfo

# MTA GTFS feed for N/Q/R/W trains
FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw"
API_KEY = "Z276E3rCeTzOQEoBPPN4JCEc6GfvdnYE"  # ⬅️ replace with your real x-api-key

# Stop IDs for 59th St – Lexington Ave (downtown platform)
TARGET_STOP_IDS = {"R15S", "R16S", "R17S"}

def get_subway_arrivals():
    headers = {"x-api-key": API_KEY}
    feed = gtfs_realtime_pb2.FeedMessage()

    try:
        response = requests.get(FEED_URL, headers=headers, timeout=10)
        response.raise_for_status()
        feed.ParseFromString(response.content)
    except Exception as e:
        return [f"🚧 MTA Feed error: {e}"]

    # Current UTC time and buffered time (allow for travel to station)
    now_real = datetime.datetime.now(datetime.timezone.utc)
    now_buffered = now_real + datetime.timedelta(minutes=5)

    arrivals = []

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        for update in entity.trip_update.stop_time_update:
            stop_id = update.stop_id
            if stop_id not in TARGET_STOP_IDS:
                continue
            if not update.HasField("arrival") or not update.arrival.HasField("time"):
                continue

            arrival_time_unix = update.arrival.time
            arrival_dt = datetime.datetime.fromtimestamp(arrival_time_unix, tz=datetime.timezone.utc)

            # Skip trains arriving too soon
            if arrival_dt <= now_buffered:
                continue

            minutes_away = math.ceil((arrival_dt - now_real).total_seconds() / 60)
            route = entity.trip_update.trip.route_id

            # Convert to Eastern Time (local)
            arrival_et_dt = arrival_dt.astimezone(ZoneInfo("America/New_York"))
            arrival_et_str = arrival_et_dt.strftime("%-I:%M %p")

            arrivals.append((minutes_away, route, arrival_et_str))

    arrivals.sort(key=lambda x: x[0])
    return [
        f"{route} train at {arrival_time} ({mins} min)"
        for mins, route, arrival_time in arrivals[:3]
    ]
