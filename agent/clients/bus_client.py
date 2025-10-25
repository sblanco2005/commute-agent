# agent/clients/bus_client.py

import os, json, time, requests, math, xml.etree.ElementTree as ET, asyncio
from datetime import datetime, timedelta
from typing import Optional, List

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

class NJTransitBusAPIClient:
    # Stop coordinates for known stops (Fanwood)
    STOP_COORDS = {
        "28883": (40.64105108650974, -74.38512857116454)
    }

    def __init__(self, username, password, base_url, token_cache_path="bus_token.json"):
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.token_cache_path = token_cache_path
        self.token = self._load_cached_token() or self._fetch_and_cache_token()
        # MyBusNow base URL for GPS tracking
        self.mybusnow_base = "https://mybusnow.njtransit.com"

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

    def get_bus_live_trips_from_stop(self, route: str = "113", stop: str = "28883") -> List[dict]:
        """
        Gets accurate live bus predictions for a specific stop using getStopPredictions endpoint.
        Only returns buses that will actually serve this stop with official ETAs.
        Uses Playwright to bypass Cloudflare protection.
        """
        try:
            # Fetch official stop predictions (only buses serving this stop)
            xml_text = self._fetch_stop_predictions_with_browser(stop, route)
            if not xml_text:
                print("⚠️ Could not fetch stop predictions")
                return []

            # Parse predictions
            predictions = self._parse_stop_predictions_xml(xml_text)

            if not predictions:
                print("⚠️ No predictions available for this stop")
                return []

            # Convert to trip info format
            enhanced_trips = []
            for vid, pred in predictions.items():
                trip_info = {
                    "vehicle_id": vid,
                    "route": pred["route"],
                    "header": pred["route_desc"],
                    "status": pred["route_desc"],
                    "departure_time": pred["eta_text"],
                    "scheduled_time": "N/A",
                    "passenger_load": "N/A",
                    # Real-time prediction data
                    "realtime_arrival": pred["eta_text"],
                    "eta_minutes": pred["eta_min"],
                    "bus_id": vid,
                    "stop_status": pred["route_desc"],
                    "has_realtime": not pred["is_scheduled"],
                    "is_scheduled": pred["is_scheduled"]
                }
                enhanced_trips.append(trip_info)

            # Sort by ETA (earliest first)
            enhanced_trips.sort(key=lambda x: x["eta_minutes"] if x["eta_minutes"] is not None else 9999)

            return enhanced_trips

        except Exception as e:
            print(f"❌ Live bus trip error: {e}")
            return []

    def _haversine(self, lat1, lon1, lat2, lon2):
        """Calculate distance in meters between two GPS coordinates."""
        R = 6371000.0  # Earth radius in meters
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlmb = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlmb/2)**2
        return 2 * R * math.asin(math.sqrt(a))

    def _meters_to_min_sec(self, meters, avg_speed_mps=8.33):
        """Convert meters to minutes:seconds assuming avg speed ~30 km/h (8.33 m/s)."""
        if meters is None:
            return None
        total_seconds = int(meters / avg_speed_mps)
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}:{seconds:02d}"

    def _parse_bus_positions_xml(self, xml_text):
        """Parse getBusesForRoute.jsp XML response into list of bus dicts."""
        buses = []
        try:
            root = ET.fromstring(xml_text)
            for bus in root.findall(".//bus"):
                try:
                    buses.append({
                        "id": (bus.findtext("id") or "").strip(),
                        "rt": (bus.findtext("rt") or "").strip(),
                        "lat": float(bus.findtext("lat")),
                        "lon": float(bus.findtext("lon")),
                        "hdg": (bus.findtext("hdg") or bus.findtext("dn") or "").strip(),
                        "status": (bus.findtext("pd") or "").strip(),  # destination
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"⚠️ Error parsing bus positions XML: {e}")
        return buses

    def _parse_stop_predictions_xml(self, xml_text):
        """
        Parse getStopPredictions.jsp XML response.
        NJ Transit uses <pre> elements with structure:
        <pre><pt>38 MIN</pt><v>21011</v><fd>113S NEW YORK SALEM ROAD</fd></pre>
        Returns: {vehicle_id: {"eta_min": int, "eta_text": str, "route_desc": str, ...}}
        """
        predictions = {}
        try:
            root = ET.fromstring(xml_text)

            # Parse <pre> elements (NJ Transit format)
            for pre in root.findall(".//pre"):
                vid = (pre.findtext("v") or "").strip()  # Vehicle ID
                pt = (pre.findtext("pt") or "").strip()  # Prediction time: "38 MIN"
                fd = (pre.findtext("fd") or "").strip()  # Full description: "113S  NEW YORK SALEM ROAD"
                rn = (pre.findtext("rn") or "").strip()  # Route number
                scheduled = (pre.findtext("scheduled") or "").strip()  # "true" or "false"

                if vid:
                    # Parse minutes from "38 MIN" format
                    eta_min = None
                    if pt:
                        if pt.upper() in ("DUE", "BRD", "APPROACHING"):
                            eta_min = 0
                        else:
                            # Extract number from "38 MIN"
                            parts = pt.split()
                            if parts and parts[0].isdigit():
                                try:
                                    eta_min = int(parts[0])
                                except:
                                    pass

                    predictions[vid] = {
                        "eta_min": eta_min,
                        "eta_text": pt,
                        "route_desc": fd,
                        "route": rn,
                        "is_scheduled": scheduled.lower() == "true"
                    }

        except Exception as e:
            print(f"⚠️ Error parsing stop predictions XML: {e}")

        return predictions

    async def _fetch_gps_data_with_browser_async(self, route: str) -> Optional[str]:
        """Use Playwright async API to bypass Cloudflare and fetch GPS data."""
        if not PLAYWRIGHT_AVAILABLE:
            print("⚠️ Playwright not available. Install with: pip install playwright && playwright install chromium")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
                    locale="en-US"
                )
                page = await context.new_page()

                # Visit main page first to establish session
                try:
                    await page.goto(self.mybusnow_base, wait_until="domcontentloaded", timeout=30000)
                except PWTimeoutError:
                    pass

                # Fetch the GPS data using JavaScript
                url = f"{self.mybusnow_base}/bustime/map/getBusesForRoute.jsp?route={route}"
                js = """
                async (url) => {
                  try {
                    const r = await fetch(url, {
                      credentials: 'include',
                      headers: { 'Accept': '*/*' }
                    });
                    const t = await r.text();
                    return { ok: (r.status === 200), status: r.status, text: t };
                  } catch (err) {
                    return { ok: false, error: String(err) };
                  }
                }
                """
                res = await page.evaluate(js, url)
                await browser.close()

                if not isinstance(res, dict) or not res.get("ok"):
                    print(f"⚠️ Browser fetch failed: {res}")
                    return None

                return res["text"]

        except Exception as e:
            print(f"⚠️ Playwright fetch error: {e}")
            return None

    def _fetch_gps_data_with_browser(self, route: str) -> Optional[str]:
        """Synchronous wrapper for async Playwright fetch using nest_asyncio."""
        import nest_asyncio
        nest_asyncio.apply()

        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self._fetch_gps_data_with_browser_async(route))
        except Exception as e:
            print(f"⚠️ Error running async fetch: {e}")
            return None

    async def _fetch_stop_predictions_async(self, stop: str, route: str) -> Optional[str]:
        """Fetch stop predictions using Playwright to bypass Cloudflare."""
        if not PLAYWRIGHT_AVAILABLE:
            print("⚠️ Playwright not available. Install with: pip install playwright && playwright install chromium")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
                    locale="en-US"
                )
                page = await context.new_page()

                # Visit main page first to establish session
                try:
                    await page.goto(self.mybusnow_base, wait_until="domcontentloaded", timeout=30000)
                except PWTimeoutError:
                    pass

                # Fetch stop predictions
                url = f"{self.mybusnow_base}/bustime/map/getStopPredictions.jsp?stop={stop}&route={route}"
                js = """
                async (url) => {
                  try {
                    const r = await fetch(url, {
                      credentials: 'include',
                      headers: { 'Accept': '*/*' }
                    });
                    const t = await r.text();
                    return { ok: (r.status === 200), status: r.status, text: t };
                  } catch (err) {
                    return { ok: false, error: String(err) };
                  }
                }
                """
                res = await page.evaluate(js, url)
                await browser.close()

                if not isinstance(res, dict) or not res.get("ok"):
                    print(f"⚠️ Browser fetch failed: {res}")
                    return None

                return res["text"]

        except Exception as e:
            print(f"⚠️ Playwright fetch error: {e}")
            return None

    def _fetch_stop_predictions_with_browser(self, stop: str, route: str) -> Optional[str]:
        """Synchronous wrapper for async stop predictions fetch."""
        import nest_asyncio
        nest_asyncio.apply()

        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self._fetch_stop_predictions_async(stop, route))
        except Exception as e:
            print(f"⚠️ Error running async fetch: {e}")
            return None

    def _get_trip_realtime_info(self, internal_trip_number: str, sched_dep_time: str,
                                 timing_point_id: str, target_stop: str) -> dict:
        """
        Gets GPS-based real-time arrival info by fetching live bus positions.
        Filters by status 'New York' and calculates distance to stop.
        """
        try:
            # Get route from internal trip number if possible, default to 113
            route = "113"

            # Fetch live bus positions from MyBusNow
            url = f"{self.mybusnow_base}/bustime/map/getBusesForRoute.jsp?route={route}"
            res = requests.get(url, timeout=10)
            res.raise_for_status()

            buses = self._parse_bus_positions_xml(res.text)

            # Filter buses heading to New York
            ny_buses = [b for b in buses if "new york" in b["status"].lower()]

            if not ny_buses:
                return {"has_realtime": False}

            # Get stop coordinates
            if target_stop not in self.STOP_COORDS:
                return {"has_realtime": False}

            stop_lat, stop_lon = self.STOP_COORDS[target_stop]

            # Calculate distances and find closest
            for bus in ny_buses:
                bus["distance_m"] = round(self._haversine(stop_lat, stop_lon, bus["lat"], bus["lon"]))

            # Sort by distance
            ny_buses.sort(key=lambda x: x["distance_m"])
            closest = ny_buses[0]

            eta_str = self._meters_to_min_sec(closest["distance_m"])

            return {
                "realtime_arrival": eta_str,
                "distance_meters": closest["distance_m"],
                "bus_id": closest["id"],
                "stop_status": closest["status"],
                "has_realtime": True
            }

        except Exception as e:
            print(f"⚠️ Could not get GPS real-time info: {e}")
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