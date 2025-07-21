import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Optional
import html
from html import unescape
from typing import List

class NJTransitAPIClient:
    def __init__(self, username: str, password: str, base_url: str, token_cache_path: str = "cached_token.json"):
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
                print("🔐 Loaded token from cache.")
                return token_info["token"]
            else:
                print("⏳ Cached token expired.")
        except Exception as e:
            print(f"⚠️ Failed to read cached token: {e}")
        return None

    
    def _fetch_and_cache_token(self) -> Optional[str]:
        url = f"{self.base_url}/api/TrainData/getToken"
        files = {
            "username": (None, self.username),
            "password": (None, self.password)
        }
        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            print("🔁 Token response:", res.status_code, res.text)
            res.raise_for_status()
            data = res.json()
            token = data.get("UserToken")
            if token:
                print("✅ Token fetched:", token[:10] + "..." + token[-5:])

                # ⏰ Set expiration to local midnight
                now = datetime.now()
                midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                midnight_ts = midnight.timestamp()

                with open(self.token_cache_path, "w") as f:
                    json.dump({"token": token, "expires": midnight_ts}, f)

                return token
            else:
                print("❌ No token in response.")
        except Exception as e:
            print(f"❌ Error fetching token: {e}")
        return None
    
    def get_train_schedule(self, station_code: str = "NY", limit: int = 2) -> dict:
        url = f"{self.base_url}/api/TrainData/getTrainSchedule"
        files = {
            "token": (None, self.token),
            "station": (None, station_code)
        }

        allowed_lines = {"NEC", "RARV", "NJCL"}  # RVL is 'RARV', NJCL is correct, NEC is correct

        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            res.raise_for_status()
            data = res.json()
            trains = []

            for item in data.get("ITEMS", []):
                line = item.get("LINEABBREVIATION", "").upper()
                destination = item.get("DESTINATION", "").lower()

                if line not in allowed_lines:
                    continue

                sched_time = datetime.strptime(item["SCHED_DEP_DATE"], "%d-%b-%Y %I:%M:%S %p")
                formatted_time = sched_time.strftime("%I:%M %p")
                delay_min = int(item.get("SEC_LATE", "0")) // 60
                delay_status = "DELAYED" if delay_min > 0 else "ON TIME"
                
               

                destination_raw = item.get("DESTINATION", "N/A")
                destination = unescape(destination_raw)  # turns '&#9992' into '✈️'

                trains.append({
                "line": line,
                "train_id": item.get("TRAIN_ID", "N/A"),
                "destination": destination,
                "time": formatted_time,
                "track": item.get("TRACK") or "?",
                "status": delay_status,
            })
                if len(trains) >= limit:
                    break

            return {
                "next_trains": trains,
                "delayed": any(t["status"] == "DELAYED" for t in trains)
            }

        except Exception as e:
            print(f"❌ Schedule fetch error: {e}")
            return {
                "next_trains": [],
                "delayed": False,
                "error": str(e)
            }
    def get_station_alerts(self, station_code: str = "NY") -> List[str]:
        """
        Fetches alert banner messages for a specific station.
        """
        url = f"{self.base_url}/api/TrainData/getStationMSG"
        files = {
            "token": (None, self.token),
            "station": (None, station_code),
            "line": (None, "")
        }

        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            res.raise_for_status()
            messages = res.json()
            return [msg.get("MSG_TEXT", "").strip() for msg in messages if msg.get("MSG_TEXT")]
        except Exception as e:
            print(f"❌ Station alert fetch error: {e}")
            return []
        

    def get_bus_locations_data(self, route: str, direction: str, lat: float, lon: float, radius_feet: int = 2000) -> List[dict]:
        url = f"{self.base_url}/api/BUSDV2/getBusLocationsData"
        files = {
            "token": (None, self.token),
            "route": (None, route),
            "direction": (None, direction),
            "lat": (None, str(lat)),
            "lon": (None, str(lon)),
            "radius": (None, str(radius_feet)),
            "mode": (None, "BUS")
        }

        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            res.raise_for_status()
            data = res.json()

            return [{
                "stop": item.get("busstopdescription", "Unknown"),
                "distance_ft": item.get("distance", "?"),
                "lat": item.get("latitude"),
                "lon": item.get("longitude")
            } for item in data]

        except Exception as e:
            print(f"❌ Bus location fetch error: {e}")
            return []
            
    def get_bus_schedule_113x(self, location_code="PABT", route="113", limit: int = 3) -> dict:
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

            buses = []
            for item in data[:limit]:
                buses.append({
                    "route": item.get("public_route", "N/A"),
                    "header": item.get("header", "").strip(),
                    "time": item.get("departuretime", "N/A"),
                    "lanegate": item.get("lanegate", "").strip(),
                    "remarks": item.get("remarks", "").strip()
                })

            # 🔍 Now fetch bus locations near 113X
            locations = self.get_bus_locations_data(route="113", direction="New York", lat=40.64101, lon=-74.38390)

            return {
                "next_buses": buses,
                "nearby_bus_locations": locations,
                "delayed": any("DELAY" in b["remarks"].upper() for b in buses)
            }

        except Exception as e:
            print(f"❌ 113X bus schedule fetch error: {e}")
            return {
                "next_buses": [],
                "nearby_bus_locations": [],
                "delayed": False,
                "error": str(e)
            }