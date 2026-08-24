from __future__ import annotations

import logging
import threading
import time
from copy import deepcopy
from datetime import datetime
from typing import Any

import requests

from config import CONFIG

LOGGER = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_cache_lock = threading.Lock()
_cache_timestamp = 0.0
_cache_data: dict[str, Any] | None = None
_last_successful_data: dict[str, Any] | None = None
_location_cache: dict[str, Any] | None = None


def _empty(error: str | None = None) -> dict[str, Any]:
    return {
        "available": False,
        "temperature": None,
        "apparent_temperature": None,
        "temperature_unit": "°F",
        "location": None,
        "updated_at": None,
        "source": "Open-Meteo",
        "error": error,
    }


def _resolve_location() -> dict[str, Any] | None:
    global _location_cache

    if _location_cache is not None:
        return deepcopy(_location_cache)

    zip_code = CONFIG["airnow_zip"]
    if not zip_code:
        return None

    response = requests.get(
        GEOCODING_URL,
        params={
            "name": zip_code,
            "count": 10,
            "language": "en",
            "format": "json",
            "countryCode": "US",
        },
        timeout=CONFIG["outdoor_weather_timeout_seconds"],
    )
    response.raise_for_status()
    payload = response.json()

    results = payload.get("results") if isinstance(payload, dict) else None
    if not results:
        return None

    exact = next(
        (
            result
            for result in results
            if zip_code in (result.get("postcodes") or [])
        ),
        results[0],
    )

    _location_cache = {
        "latitude": exact.get("latitude"),
        "longitude": exact.get("longitude"),
        "name": exact.get("name"),
        "admin1": exact.get("admin1"),
        "timezone": exact.get("timezone") or "auto",
    }
    return deepcopy(_location_cache)


def _fetch() -> dict[str, Any]:
    if not CONFIG["outdoor_weather_enabled"]:
        return _empty("Outdoor weather is disabled.")

    if not CONFIG["airnow_zip"]:
        return _empty("AIRNOW_ZIP is not configured.")

    try:
        location = _resolve_location()
        if not location:
            return _empty(
                f"Open-Meteo could not resolve ZIP {CONFIG['airnow_zip']}."
            )

        response = requests.get(
            FORECAST_URL,
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "current": "temperature_2m,apparent_temperature",
                "temperature_unit": "fahrenheit",
                "timezone": location["timezone"],
            },
            timeout=CONFIG["outdoor_weather_timeout_seconds"],
        )
        response.raise_for_status()
        payload = response.json()
        current = payload.get("current") or {}

        temperature = current.get("temperature_2m")
        apparent = current.get("apparent_temperature")
        if temperature is None:
            return _empty("Open-Meteo returned no current temperature.")

        return {
            "available": True,
            "temperature": round(float(temperature), 1),
            "apparent_temperature": (
                round(float(apparent), 1)
                if apparent is not None
                else None
            ),
            "temperature_unit": "°F",
            "location": location.get("name"),
            "updated_at": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "source": "Open-Meteo",
            "error": None,
        }
    except requests.RequestException as exc:
        LOGGER.warning("Open-Meteo request failed: %s", exc)
        return _empty(f"Open-Meteo request failed: {exc}")
    except (TypeError, ValueError) as exc:
        LOGGER.warning("Open-Meteo response parsing failed: %s", exc)
        return _empty("Open-Meteo returned an invalid response.")


def get_outdoor_weather(force_refresh: bool = False) -> dict[str, Any]:
    global _cache_data, _cache_timestamp, _last_successful_data

    now = time.monotonic()
    with _cache_lock:
        valid = (
            not force_refresh
            and _cache_data is not None
            and now - _cache_timestamp
            < CONFIG["outdoor_weather_cache_seconds"]
        )
        if valid:
            return deepcopy(_cache_data)

    fresh = _fetch()

    with _cache_lock:
        if fresh.get("available"):
            fresh["stale"] = False
            _last_successful_data = deepcopy(fresh)
            _cache_data = fresh
        elif _last_successful_data is not None:
            stale = deepcopy(_last_successful_data)
            stale["stale"] = True
            stale["error"] = fresh.get("error")
            _cache_data = stale
        else:
            fresh["stale"] = False
            _cache_data = fresh

        _cache_timestamp = time.monotonic()
        return deepcopy(_cache_data)
