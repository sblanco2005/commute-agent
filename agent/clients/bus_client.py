# agent/clients/bus_client.py

import os, json, time, requests
from datetime import datetime, timedelta
from typing import Optional, List
from html import unescape

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
        Replaces the older getBusLocationsData which returns empty often.
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
            #print(data)
            live_trips = data.get("DVTrip", [])
            #print(live_trips)
            return [{
                "vehicle_id": trip.get("vehicle_id"),
                "departure_time": trip.get("departuretime"),
                "status": trip.get("departurestatus"),
                "header": trip.get("header", "").strip()
            } for trip in live_trips]

        except Exception as e:
            print(f"❌ Live bus trip error: {e}")
            return []

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