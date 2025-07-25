# agent/clients/rail_client.py

import os, json, time, requests
from datetime import datetime, timedelta
from typing import Optional
from html import unescape

class NJTransitRailAPIClient:
    def __init__(self, username, password, base_url, token_cache_path="rail_token.json"):
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
                print("🔐 (RAIL) Loaded token from cache.")
                return token_info["token"]
        except Exception as e:
            print(f"⚠️ Failed to read rail token: {e}")
        return None

    def _fetch_and_cache_token(self) -> Optional[str]:
        url = f"{self.base_url}/api/TrainData/getToken"
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
                print("✅ (RAIL) Token fetched.")
                midnight = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                with open(self.token_cache_path, "w") as f:
                    json.dump({"token": token, "expires": midnight.timestamp()}, f)
                return token
        except Exception as e:
            print(f"❌ Error fetching rail token: {e}")
        return None

    def get_train_schedule(self, station_code="NY", limit=3) -> dict:
        url = f"{self.base_url}/api/TrainData/getTrainSchedule"
        files = {
            "token": (None, self.token),
            "station": (None, station_code)
        }
        if station_code=="NY":
            allowed_lines = {"NEC", "RARV", "NJCL"}
        elif station_code=="NP":
             allowed_lines = {"RARV"}
        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            res.raise_for_status()
            data = res.json()
            trains = []
            for item in data.get("ITEMS", []):
                line = item.get("LINEABBREVIATION", "").upper()
                if line not in allowed_lines:
                    continue
                sched_time = datetime.strptime(item["SCHED_DEP_DATE"], "%d-%b-%Y %I:%M:%S %p")
                trains.append({
                    "line": line,
                    "destination": unescape(item.get("DESTINATION", "N/A")),
                    "time": sched_time.strftime("%I:%M %p"),
                    "track": item.get("TRACK") or "?",
                    "status": "DELAYED" if int(item.get("SEC_LATE", "0")) > 0 else "ON TIME"
                })
                if len(trains) >= limit:
                    break
            return {"next_trains": trains, "delayed": any(t["status"] == "DELAYED" for t in trains)}
        except Exception as e:
            print(f"❌ Train schedule error: {e}")
            return {"next_trains": [], "delayed": False, "error": str(e)}

    def get_station_alerts(self, station_code="NY"):
        url = f"{self.base_url}/api/TrainData/getStationMSG"
        files = {
            "token": (None, self.token),
            "station": (None, station_code),
            "line": (None, "")
        }
        try:
            res = requests.post(url, files=files, headers={"accept": "text/plain"}, timeout=10)
            res.raise_for_status()
            return [msg.get("MSG_TEXT", "").strip() for msg in res.json() if msg.get("MSG_TEXT")]
        except Exception as e:
            print(f"❌ Station alert fetch error: {e}")
            return []