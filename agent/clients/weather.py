import httpx

async def get_weather_alerts_by_coords(api_key: str, lat: float, lon: float):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    print(f"🌤 Async fetching: {url}")

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        weather_list = data.get("weather", [])
        description = weather_list[0]["description"] if weather_list else "Clear"
        temp_celsius = data["main"]["temp"]
        conditions = [w["main"].lower() for w in weather_list]
        is_bad = any(c in {"thunderstorm", "rain", "snow"} for c in conditions)

        return {
            "is_bad": is_bad,
            "description": description,
            "temp_celsius": temp_celsius,
            "alerts": [],  # optional: add alert parsing if using One Call API
        }
    except httpx.RequestError as e:
        print(f"⚠️ Async request error: {repr(e)}")
    except httpx.HTTPStatusError as e:
        print(f"⚠️ HTTP error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")

    return {
        "is_bad": False,
        "description": "Unavailable",
        "temp_celsius": "N/A",
        "alerts": [],
    }