#!/usr/bin/env python3
"""
Diagnostic tool to inspect MTA GTFS feed for specific stops
Usage: python check_stop.py [stop_id]
Example: python check_stop.py R15S
"""

import sys
import os
import requests
from google.transit import gtfs_realtime_pb2
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw"
API_KEY = os.getenv("MTA_API_KEY")

def fetch_feed():
    """Fetch and parse the GTFS feed"""
    headers = {"x-api-key": API_KEY} if API_KEY else {}
    feed = gtfs_realtime_pb2.FeedMessage()

    print(f"🔍 Fetching feed from: {FEED_URL}")
    print(f"🔑 Using API key: {'Yes' if API_KEY else 'No (public access)'}\n")

    try:
        response = requests.get(FEED_URL, headers=headers, timeout=10)
        response.raise_for_status()
        feed.ParseFromString(response.content)
        print(f"✅ Feed fetched successfully at {datetime.now().strftime('%I:%M:%S %p')}\n")
        return feed
    except Exception as e:
        print(f"❌ Error fetching feed: {e}")
        sys.exit(1)

def analyze_feed(feed, target_stop_id=None):
    """Analyze the feed and show stop information"""

    # Collect all unique stop IDs and their occurrences
    stop_counts = defaultdict(int)
    stop_routes = defaultdict(set)
    stop_arrivals = defaultdict(list)

    now = datetime.now(timezone.utc)

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        route_id = entity.trip_update.trip.route_id
        trip_id = entity.trip_update.trip.trip_id

        for update in entity.trip_update.stop_time_update:
            stop_id = update.stop_id
            stop_counts[stop_id] += 1
            stop_routes[stop_id].add(route_id)

            # If this is our target stop, collect arrival details
            if target_stop_id and stop_id == target_stop_id:
                if update.HasField("arrival") and update.arrival.HasField("time"):
                    arrival_time_unix = update.arrival.time
                    arrival_dt = datetime.fromtimestamp(arrival_time_unix, tz=timezone.utc)
                    minutes_away = round((arrival_dt - now).total_seconds() / 60, 1)

                    stop_arrivals[stop_id].append({
                        'route': route_id,
                        'trip_id': trip_id,
                        'arrival_dt': arrival_dt,
                        'minutes_away': minutes_away
                    })

    # Display results
    if target_stop_id:
        print(f"{'='*70}")
        print(f"🎯 DETAILED INFORMATION FOR STOP: {target_stop_id}")
        print(f"{'='*70}\n")

        if target_stop_id in stop_counts:
            print(f"✅ Stop found in feed!")
            print(f"   - Occurrences: {stop_counts[target_stop_id]}")
            print(f"   - Routes serving this stop: {', '.join(sorted(stop_routes[target_stop_id]))}\n")

            if stop_arrivals[target_stop_id]:
                print(f"📍 UPCOMING ARRIVALS AT {target_stop_id}:\n")

                # Sort by arrival time
                arrivals = sorted(stop_arrivals[target_stop_id], key=lambda x: x['minutes_away'])

                for i, arrival in enumerate(arrivals[:10], 1):  # Show first 10
                    local_time = arrival['arrival_dt'].astimezone()
                    time_str = local_time.strftime('%I:%M:%S %p')
                    mins = arrival['minutes_away']
                    status = "🚇 Arriving soon" if mins <= 5 else "⏰ Scheduled"

                    print(f"{i:2}. {arrival['route']:>2} train - {time_str} ({mins:+.1f} min) {status}")
                    print(f"    Trip ID: {arrival['trip_id']}")

                if len(arrivals) > 10:
                    print(f"\n    ... and {len(arrivals) - 10} more arrivals")
            else:
                print("⚠️  No arrival times found for this stop in current feed")
        else:
            print(f"❌ Stop '{target_stop_id}' NOT FOUND in feed\n")
            print("💡 Showing similar stop IDs that might help:\n")

            # Show stops that start with same letter or contain target
            similar = [s for s in stop_counts.keys() if s.startswith(target_stop_id[0]) or target_stop_id[1:] in s]
            for stop in sorted(similar)[:20]:
                routes = ', '.join(sorted(stop_routes[stop]))
                print(f"   - {stop:8} (Routes: {routes}, Count: {stop_counts[stop]})")

    # Always show summary statistics
    print(f"\n{'='*70}")
    print(f"📊 FEED SUMMARY")
    print(f"{'='*70}\n")
    print(f"Total unique stops in feed: {len(stop_counts)}")
    print(f"Total stop updates: {sum(stop_counts.values())}")

    # Show all stops starting with 'R15' (Lexington Ave line)
    print(f"\n🔎 All stops starting with 'R15' (59th St-Lex area):\n")
    r15_stops = {k: v for k, v in stop_counts.items() if k.startswith('R15')}
    if r15_stops:
        for stop in sorted(r15_stops.keys()):
            routes = ', '.join(sorted(stop_routes[stop]))
            print(f"   - {stop:8} (Routes: {routes}, Count: {stop_counts[stop]})")
    else:
        print("   ⚠️  No stops found starting with 'R15'")

    # Show sample of all stop IDs (first 20)
    print(f"\n📝 Sample of all stop IDs in feed (first 30):\n")
    for i, stop in enumerate(sorted(stop_counts.keys())[:30], 1):
        routes = ', '.join(sorted(stop_routes[stop]))
        print(f"   {i:2}. {stop:8} (Routes: {routes})")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "R15S"

    print(f"\n{'='*70}")
    print(f"  MTA GTFS FEED STOP INSPECTOR")
    print(f"{'='*70}\n")

    feed = fetch_feed()
    analyze_feed(feed, target)

    print(f"\n{'='*70}\n")
