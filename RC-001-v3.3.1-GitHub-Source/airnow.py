from __future__ import annotations

import json
import logging
import threading
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from config import BASE_DIR, CONFIG


LOGGER = logging.getLogger(__name__)
AIRNOW_URL = "https://www.airnowapi.org/aq/observation/zipCode/current/"
LAST_GOOD_FILE = Path(BASE_DIR) / "data" / "airnow_last_good.json"

_cache_lock = threading.Lock()
_cache_timestamp = 0.0
_cache_data: dict[str, Any] | None = None
_last_good_data: dict[str, Any] | None = None


def _metadata(aqi: int | None) -> dict[str, Any]:
    bands = [
        (50, "Good", "good", 0, "Air quality is satisfactory."),
        (100, "Moderate", "moderate", 1,
         "Air quality is acceptable. Unusually sensitive people may experience minor effects."),
        (150, "Unhealthy for Sensitive Groups", "sensitive", 2,
         "Sensitive groups should reduce prolonged or heavy outdoor activity."),
        (200, "Unhealthy", "unhealthy", 3,
         "Everyone should reduce prolonged or heavy outdoor activity."),
        (300, "Very Unhealthy", "very_unhealthy", 4,
         "Avoid prolonged or heavy outdoor activity whenever possible."),
        (10000, "Hazardous", "hazardous", 5,
         "Avoid outdoor physical activity and keep indoor air as clean as possible."),
    ]
    if aqi is None:
        return {
            "category": "Unavailable", "level": "unknown", "rank": -1,
            "health_message": "Air-quality data is currently unavailable.",
        }
    for upper, category, level, rank, message in bands:
        if aqi <= upper:
            return {
                "category": category, "level": level, "rank": rank,
                "health_message": message,
            }
    raise AssertionError("AQI band lookup failed")


def _empty(error: str | None = None) -> dict[str, Any]:
    info = _metadata(None)
    return {
        "available": False, "live_available": False, "is_fresh": False,
        "data_status": "unavailable", "age_seconds": None,
        "configured": bool(CONFIG["airnow_api_key"] and CONFIG["airnow_zip"]),
        "aqi": None, "category": info["category"], "level": info["level"],
        "rank": info["rank"], "health_message": info["health_message"],
        "pollutant": None, "reporting_area": None, "state_code": None,
        "source": "EPA AirNow", "zip_code": CONFIG["airnow_zip"] or None,
        "updated_at": None, "received_at_epoch": None, "fetch_id": None,
        "error": error, "observations": [],
    }


def _request_once() -> dict[str, Any]:
    params = {
        "format": "application/json", "zipCode": CONFIG["airnow_zip"],
        "distance": CONFIG["airnow_distance"], "API_KEY": CONFIG["airnow_api_key"],
    }
    response = requests.get(
        AIRNOW_URL, params=params, timeout=CONFIG["airnow_timeout_seconds"]
    )
    response.raise_for_status()
    payload = response.json()
    observations = []
    for item in payload if isinstance(payload, list) else []:
        try:
            aqi = int(item.get("AQI"))
        except (TypeError, ValueError):
            continue
        observations.append({
            "aqi": aqi, "pollutant": item.get("ParameterName"),
            "reporting_area": item.get("ReportingArea"),
            "state_code": item.get("StateCode"),
            "date_observed": item.get("DateObserved"),
            "hour_observed": item.get("HourObserved"),
            "local_time_zone": item.get("LocalTimeZone"),
        })
    if not observations:
        return _empty("AirNow returned no current AQI observations.")

    highest = max(observations, key=lambda item: item["aqi"])
    info = _metadata(highest["aqi"])
    now = int(time.time())
    return {
        "available": True, "live_available": True, "is_fresh": True,
        "data_status": "current", "age_seconds": 0,
        "configured": True, "aqi": highest["aqi"],
        "category": info["category"], "level": info["level"], "rank": info["rank"],
        "health_message": info["health_message"],
        "pollutant": highest["pollutant"],
        "reporting_area": highest["reporting_area"],
        "state_code": highest["state_code"],
        "source": "EPA AirNow", "zip_code": CONFIG["airnow_zip"],
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "received_at_epoch": now, "fetch_id": str(time.time_ns()),
        "error": None, "observations": observations,
    }


def _fetch() -> dict[str, Any]:
    if not CONFIG["airnow_api_key"]:
        return _empty("AIRNOW_API_KEY is not configured.")
    if not CONFIG["airnow_zip"]:
        return _empty("AIRNOW_ZIP is not configured.")

    attempts = max(1, int(CONFIG["airnow_retry_attempts"]))
    last_error: str | None = None
    for attempt in range(attempts):
        try:
            result = _request_once()
            if result.get("live_available"):
                return result
            last_error = result.get("error")
        except requests.RequestException as exc:
            last_error = f"AirNow request failed: {exc}"
        except ValueError:
            last_error = "AirNow returned invalid JSON."
        if attempt + 1 < attempts:
            time.sleep(CONFIG["airnow_retry_backoff_seconds"] * (attempt + 1))
    LOGGER.warning("AirNow request failed after %s attempts: %s", attempts, last_error)
    return _empty(last_error or "AirNow request failed.")


def _load_last_good() -> dict[str, Any] | None:
    try:
        payload = json.loads(LAST_GOOD_FILE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) and payload.get("aqi") is not None else None
    except (OSError, ValueError):
        return None


def _save_last_good(payload: dict[str, Any]) -> None:
    try:
        LAST_GOOD_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = LAST_GOOD_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(LAST_GOOD_FILE)
    except OSError as exc:
        LOGGER.warning("Unable to persist last good AirNow reading: %s", exc)


def _fallback(error: str | None) -> dict[str, Any]:
    global _last_good_data
    if _last_good_data is None:
        _last_good_data = _load_last_good()
    if _last_good_data is None:
        return _empty(error)
    payload = deepcopy(_last_good_data)
    now = int(time.time())
    received = int(payload.get("received_at_epoch") or now)
    age = max(0, now - received)
    stale = age > CONFIG["airnow_stale_seconds"]
    payload.update(
        available=True, live_available=False, is_fresh=False,
        data_status="stale" if stale else "delayed",
        age_seconds=age, error=error,
    )
    return payload


def get_air_quality(force_refresh: bool = False) -> dict[str, Any]:
    global _cache_data, _cache_timestamp, _last_good_data
    now = time.monotonic()
    with _cache_lock:
        valid = (
            not force_refresh and _cache_data is not None
            and now - _cache_timestamp < CONFIG["airnow_cache_seconds"]
        )
        if valid:
            cached = deepcopy(_cache_data)
            if cached.get("received_at_epoch"):
                age = max(0, int(time.time()) - int(cached["received_at_epoch"]))
                cached["age_seconds"] = age
                if not cached.get("is_fresh"):
                    cached["data_status"] = (
                        "stale" if age > CONFIG["airnow_stale_seconds"] else "delayed"
                    )
            return cached

    fresh = _fetch()
    if fresh.get("live_available"):
        _last_good_data = deepcopy(fresh)
        _save_last_good(fresh)
        result = fresh
    else:
        result = _fallback(fresh.get("error"))
    with _cache_lock:
        _cache_data = deepcopy(result)
        _cache_timestamp = time.monotonic()
        return deepcopy(result)
