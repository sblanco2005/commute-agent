# agent/clients/bus_client.py

import os, json, time, requests
from datetime import datetime, timedelta
from typing import Optional, List

class NJTransitBusAPIClient:
    def __init__(self, username, password, base_url, token_cache_path="bus_token.json"):
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.token_cache_path = token_cache_path
        self.token = self._load_cached_token() or self._fetch_and_cache_token()

    def _load_cached_token(self) -> Optional[str]:
        if not os.path.exists(self.token_cache_path):
            return None
        try:
            with open(self.token_cache_path, "r") as f:
                token_info = json.load(f)
            if time.time() < token_info.get("expires", 0):
                print("🔐 (BUS) Loaded token from cache.")
                return token_info["token"]
        except Exception as e:
            print(f"⚠️ Failed to read bus token: {e}")
        return None

    def _fetch_and_cache_token(self) -> Optional[str]:
        url = f"{self.base_url}/api/BUSDV2/authenticateUser"
        files = {
            "username": (None, self.username),
            "password": (None, self.password)
        }
        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            res.raise_for_status()
            data = res.json()
            token = data.get("UserToken")
            if token:
                print("✅ (BUS) Token fetched.")
                midnight = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                with open(self.token_cache_path, "w") as f:
                    json.dump({"token": token, "expires": midnight.timestamp()}, f)
                return token
        except Exception as e:
            print(f"❌ Error fetching bus token: {e}")
        return None

    def get_bus_schedule_to_nyc(self, location_code="28883", route="113", limit=3) -> dict:
        """
        Gets upcoming 113 buses departing from a NJ origin (e.g., Fanwood) to Port Authority.
        """
        url = f"{self.base_url}/api/BUSDV2/getRouteTrips"
        files = {
            "token": (None, self.token),
            "location": (None, location_code),
            "route": (None, route)
        }
        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            res.raise_for_status()
            data = res.json()

            # Assume buses from Fanwood are going to NYC
            buses = [{
                "route": item.get("public_route", "N/A"),
                "header": item.get("header", "").strip(),
                "time": item.get("departuretime", "N/A"),
                "remarks": item.get("remarks", "").strip()
            } for item in data][:limit]

            return {
                "next_buses": buses,
                "delayed": any("DELAY" in b["remarks"].upper() for b in buses)
            }
        except Exception as e:
            print(f"❌ 113 to NYC schedule error: {e}")
            return {"next_buses": [], "delayed": False, "error": str(e)}

    def get_bus_live_trips_from_stop(self, route: str = "113", direction: str = "New York", stop: str = "28883") -> List[dict]:
        """
        Gets live bus trips for a given route and direction from a known stop (e.g., Fanwood).
        Now enhanced with real-time arrival estimates from getTripStops.
        """
        url = f"{self.base_url}/api/BUSDV2/getBusDV"
        files = {
            "token": (None, self.token),
            "route": (None, route),
            "direction": (None, direction),
            "stop": (None, stop)
        }

        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            res.raise_for_status()
            data = res.json()
            live_trips = data.get("DVTrip", [])

            # Enhance each trip with real-time stop information
            enhanced_trips = []
            for trip in live_trips:
                trip_info = {
                    "vehicle_id": trip.get("vehicle_id"),
                    "departure_time": trip.get("departuretime"),
                    "scheduled_time": trip.get("sched_dep_time"),
                    "status": trip.get("departurestatus"),
                    "header": trip.get("header", "").strip(),
                    "route": trip.get("public_route"),
                    "passenger_load": trip.get("passload")
                }

                # Get real-time stop updates if we have trip details
                internal_trip_number = trip.get("internal_trip_number")
                if internal_trip_number:
                    realtime_info = self._get_trip_realtime_info(
                        internal_trip_number=internal_trip_number,
                        sched_dep_time=trip.get("sched_dep_time"),
                        timing_point_id=trip.get("timing_point_id"),
                        target_stop=stop
                    )
                    trip_info.update(realtime_info)

                enhanced_trips.append(trip_info)

            return enhanced_trips

        except Exception as e:
            print(f"❌ Live bus trip error: {e}")
            return []

    def _get_trip_realtime_info(self, internal_trip_number: str, sched_dep_time: str,
                                 timing_point_id: str, target_stop: str) -> dict:
        """
        Gets real-time stop information for a specific trip.
        Returns approximate arrival time and status for the target stop.
        """
        url = f"{self.base_url}/api/BUSDV2/getTripStops"
        files = {
            "token": (None, self.token),
            "internal_trip_number": (None, internal_trip_number),
            "sched_dep_time": (None, sched_dep_time),
            "timing_point_id": (None, timing_point_id)
        }

        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            res.raise_for_status()
            stops = res.json()

            # Find our target stop in the trip
            for stop in stops:
                if stop.get("StopID") == target_stop:
                    approx_time = stop.get("ApproxTime")
                    stop_status = stop.get("Status")

                    return {
                        "realtime_arrival": approx_time,
                        "stop_status": stop_status,
                        "has_realtime": True
                    }

            # If stop not found, return minimal info
            return {"has_realtime": False}

        except Exception as e:
            print(f"⚠️ Could not get real-time info for trip {internal_trip_number}: {e}")
            return {"has_realtime": False}

    def get_bus_stops(self):
        url = f"{self.base_url}/api/BUSDV2/getStops"
        files = {"token": (None, self.token)}

        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            res.raise_for_status()
            data = res.json()
            print("🟡 Raw get_bus_stops data:", data)  # <== ADD THIS LINE
            return data
        except Exception as e:
            print(f"❌ Error fetching bus stops: {e}")
            return []