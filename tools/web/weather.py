import requests

import concurrent.futures
from tools.responses import tool_response
from tools.schemas import WeatherInput


def get_weather(data: WeatherInput):
    """
    Fetch weather using Open-Meteo API (fast, free, no API key)
    Docs: https://open-meteo.com/en/docs
    """
    try:
        def fetch_weather(location):
            """Fetch weather for a single location"""
            
            # Step 1: Geocode location to get coordinates
            geocode_url = f"https://geocoding-api.open-meteo.com/v1/search"
            geocode_params = {
                "name": location,
                "count": 1,
                "language": "en",
                "format": "json"
            }
            
            try:
                geo_response = requests.get(geocode_url, params=geocode_params, timeout=5)
                geo_response.raise_for_status()
                geo_data = geo_response.json()

                if not geo_data.get("results"):
                    return {
                        "location": location,
                        "error": "location not found"
                    }

                result = geo_data["results"][0]
                lat = result["latitude"]
                lon = result["longitude"]
                location_name = result.get("name", location)
                country = result.get("country", "")

            except Exception as e:
                return {
                    "location": location,
                    "error": f"geocoding failed: {str(e)}"
                }

            # Step 2: Fetch weather data
            weather_url = "https://api.open-meteo.com/v1/forecast"
            weather_params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,temperature_2m_mean",
                "timezone": "auto",
                "forecast_days": max(3, data.days_ahead + 1)  # Ensure we get enough days
            }

            try:
                weather_response = requests.get(weather_url, params=weather_params, timeout=5)
                weather_response.raise_for_status()
                weather_data = weather_response.json()

            except Exception as e:
                return {
                    "location": location,
                    "error": f"weather fetch failed: {str(e)}"
                }

            # Step 3: Parse response
            entry = {
                "location": f"{location_name}, {country}",
                "days_ahead": data.days_ahead,
            }

            if data.days_ahead == 0:
                # Current weather
                current = weather_data.get("current", {})

                if not current:
                    return {
                        "location": location,
                        "error": "weather data unavailable"
                    }

                weather_code = current.get("weather_code", 0)
                condition = _weather_code_to_description(weather_code)

                entry["weather"] = {
                    "condition": condition,
                    "temperature_c": current.get("temperature_2m"),
                    "feels_like_c": current.get("apparent_temperature"),
                    "humidity": current.get("relative_humidity_2m"),
                }
            else:
                # Forecast weather
                daily = weather_data.get("daily", {})

                if not daily or "time" not in daily:
                    return {
                        "location": location,
                        "error": "weather data unavailable"
                    }

                dates = daily.get("time", [])
                
                if data.days_ahead >= len(dates):
                    return {
                        "location": location,
                        "error": f"forecast only available for {len(dates)} days"
                    }

                idx = data.days_ahead
                weather_code = daily.get("weather_code", [])[idx]
                condition = _weather_code_to_description(weather_code)

                entry["weather"] = {
                    "date": dates[idx],
                    "condition": condition,
                    "max_temp_c": daily.get("temperature_2m_max", [])[idx],
                    "min_temp_c": daily.get("temperature_2m_min", [])[idx],
                    "avg_temp_c": daily.get("temperature_2m_mean", [])[idx],
                }

            return entry

        # Parallel execution
        results = []
        failed_locations = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_location = {
                executor.submit(fetch_weather, loc): loc 
                for loc in data.locations
            }

            for future in concurrent.futures.as_completed(future_to_location):
                location = future_to_location[future]
                try:
                    result = future.result()
                    if "error" in result:
                        failed_locations.append(location)
                    results.append(result)
                except Exception as e:
                    failed_locations.append(location)
                    results.append({
                        "location": location,
                        "error": f"request failed: {str(e)}"
                    })

        if len(failed_locations) == len(data.locations):
            return tool_response(
                tool="weather",
                success=False,
                error="weather data unavailable for all locations"
            )

        return tool_response(
            tool="weather",
            success=True,
            data=results
        )

    except Exception as e:
        return tool_response(
            tool="weather",
            success=False,
            error=f"weather tool error: {str(e)}"
        )


def _weather_code_to_description(code: int) -> str:
    """
    Convert WMO Weather Code to human-readable description
    Full list: https://open-meteo.com/en/docs
    """
    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return weather_codes.get(code, "Unknown")

