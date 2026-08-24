from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

# Load variables from RC001/.env before building CONFIG.
load_dotenv(BASE_DIR / ".env")


def _json_list(name: str) -> list[dict[str, object]]:
    """Load a list of configuration objects without embedding site details."""
    raw = os.getenv(name, "[]").strip() or "[]"
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must contain valid JSON") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{name} must be a JSON array of objects")
    return value


CONFIG = {
    "app_version": os.getenv("RC001_VERSION", "3.3.1"),
    "application_name": os.getenv(
        "RC001_APPLICATION_NAME",
        "Home Operations Center",
    ),
    "peplink_base_url": os.getenv(
        "PEPLINK_BASE_URL",
        "",
    ),
    "peplink_username": os.getenv(
        "PEPLINK_USERNAME",
        "admin",
    ),
    "peplink_password": os.getenv(
        "PEPLINK_PASSWORD",
        "",
    ),
    "wled_base_url": os.getenv(
        "WLED_BASE_URL",
        "",
    ),

    "home_assistant_url": os.getenv("HOME_ASSISTANT_URL") or None,
    "home_assistant_token": os.getenv("HOME_ASSISTANT_TOKEN") or None,
    "home_assistant_timeout_seconds": int(
        os.getenv("HOME_ASSISTANT_TIMEOUT_SECONDS", "10")
    ),

    "temperature_entity": os.getenv(
        "TEMPERATURE_ENTITY",
        "sensor.cabinet_temperature",
    ),
    "humidity_entity": os.getenv(
        "HUMIDITY_ENTITY",
        "sensor.cabinet_humidity",
    ),

    # Cabinet environmental-health thresholds. All temperatures are °F.
    "environment_temperature_warning_f": float(
        os.getenv("ENVIRONMENT_TEMPERATURE_WARNING_F", "82")
    ),
    "environment_temperature_critical_f": float(
        os.getenv("ENVIRONMENT_TEMPERATURE_CRITICAL_F", "90")
    ),
    "environment_humidity_low_warning_percent": int(
        os.getenv("ENVIRONMENT_HUMIDITY_LOW_WARNING_PERCENT", "25")
    ),
    "environment_humidity_low_critical_percent": int(
        os.getenv("ENVIRONMENT_HUMIDITY_LOW_CRITICAL_PERCENT", "15")
    ),
    "environment_humidity_high_warning_percent": int(
        os.getenv("ENVIRONMENT_HUMIDITY_HIGH_WARNING_PERCENT", "70")
    ),
    "environment_humidity_high_critical_percent": int(
        os.getenv("ENVIRONMENT_HUMIDITY_HIGH_CRITICAL_PERCENT", "80")
    ),

    "poll_seconds": int(
        os.getenv("POLL_SECONDS", "10")
    ),

    "database": Path(
        os.getenv(
            "RC001_DATABASE",
            str(BASE_DIR / "data" / "cabinet_monitor.db"),
        )
    ),

    "simulation_mode": os.getenv(
        "SIMULATION_MODE",
        "false",
    ).lower() == "true",

    "simulation_status": os.getenv(
        "SIMULATION_STATUS",
        "normal",
    ),

    "speedtest_interval_seconds": int(
        os.getenv("SPEEDTEST_INTERVAL_SECONDS", "3600")
    ),

    "speedtest_path": os.getenv(
        "SPEEDTEST_PATH",
        "speedtest",
    ),


    "snmp_enabled": os.getenv("SNMP_ENABLED", "true").lower() == "true",
    "snmp_host": os.getenv("SNMP_HOST", ""),
    "snmp_port": int(os.getenv("SNMP_PORT", "161")),
    "snmp_community": os.getenv("SNMP_COMMUNITY", "public"),
    "snmpget_path": os.getenv("SNMPGET_PATH", "snmpget"),
    "snmp_poll_seconds": float(os.getenv("SNMP_POLL_SECONDS", "2")),
    "snmp_timeout_seconds": int(os.getenv("SNMP_TIMEOUT_SECONDS", "2")),
    "snmp_retries": int(os.getenv("SNMP_RETRIES", "0")),
    "snmp_wan_ifindexes": {
        "1": int(os.getenv("SNMP_WAN1_IFINDEX", "5")),
        "2": int(os.getenv("SNMP_WAN2_IFINDEX", "6")),
        "3": int(os.getenv("SNMP_WAN3_IFINDEX", "7")),
    },

    "manual_override_seconds": int(
        os.getenv("MANUAL_OVERRIDE_SECONDS", "300")
    ),

    # EPA AirNow outdoor air-quality integration.
    "airnow_api_key": os.getenv("AIRNOW_API_KEY", "").strip(),
    "airnow_zip": os.getenv("AIRNOW_ZIP", "").strip(),
    "airnow_distance": int(os.getenv("AIRNOW_DISTANCE", "25")),
    "airnow_cache_seconds": int(os.getenv("AIRNOW_CACHE_SECONDS", "300")),
    "airnow_timeout_seconds": int(os.getenv("AIRNOW_TIMEOUT_SECONDS", "10")),
    "airnow_retry_attempts": int(os.getenv("AIRNOW_RETRY_ATTEMPTS", "3")),
    "airnow_retry_backoff_seconds": float(
        os.getenv("AIRNOW_RETRY_BACKOFF_SECONDS", "1.5")
    ),
    "airnow_stale_seconds": int(os.getenv("AIRNOW_STALE_SECONDS", "1800")),
    "airnow_history_hours": int(os.getenv("AIRNOW_HISTORY_HOURS", "24")),
    "airnow_history_store_seconds": int(
        os.getenv("AIRNOW_HISTORY_STORE_SECONDS", "900")
    ),
    "airnow_history_retention_days": int(
        os.getenv("AIRNOW_HISTORY_RETENTION_DAYS", "7")
    ),
    "airnow_trend_delta": int(os.getenv("AIRNOW_TREND_DELTA", "8")),
    "airnow_led_alerts": os.getenv(
        "AIRNOW_LED_ALERTS", "true"
    ).lower() == "true",
    "airnow_led_alert_seconds": int(
        os.getenv("AIRNOW_LED_ALERT_SECONDS", "10")
    ),

    # Open-Meteo current outdoor weather displayed with AirNow.
    "outdoor_weather_enabled": os.getenv(
        "OUTDOOR_WEATHER_ENABLED", "true"
    ).lower() == "true",
    "outdoor_weather_cache_seconds": int(
        os.getenv("OUTDOOR_WEATHER_CACHE_SECONDS", "600")
    ),
    "outdoor_weather_timeout_seconds": int(
        os.getenv("OUTDOOR_WEATHER_TIMEOUT_SECONDS", "10")
    ),

    # Browser-rendered Windy precipitation radar on the Environment page.
    "weather_radar_enabled": os.getenv(
        "WEATHER_RADAR_ENABLED", "true"
    ).lower() == "true",
    "weather_radar_latitude": float(
        os.getenv("WEATHER_RADAR_LATITUDE", "0")
    ),
    "weather_radar_longitude": float(
        os.getenv("WEATHER_RADAR_LONGITUDE", "0")
    ),
    "weather_radar_zoom": int(os.getenv("WEATHER_RADAR_ZOOM", "8")),


    # Ring camera telemetry through Home Assistant.
    "ring_timeout_seconds": int(os.getenv("RING_TIMEOUT_SECONDS", "8")),
    "ring_low_battery_percent": int(os.getenv("RING_LOW_BATTERY_PERCENT", "40")),
    "ring_critical_battery_percent": int(os.getenv("RING_CRITICAL_BATTERY_PERCENT", "20")),
    "ring_cameras": _json_list("RING_CAMERAS_JSON"),

    # RC-001 v3.1 Pushover alerting. Tokens remain in .env only.
    "pushover_enabled": os.getenv("PUSHOVER_ENABLED", "true").lower() == "true",
    "pushover_user_key": os.getenv("PUSHOVER_USER_KEY", "").strip(),
    "pushover_api_token": os.getenv("PUSHOVER_API_TOKEN", "").strip(),
    "pushover_device": os.getenv("PUSHOVER_DEVICE", "").strip(),
    "pushover_dashboard_url": os.getenv("PUSHOVER_DASHBOARD_URL", "").strip(),
    "pushover_timeout_seconds": int(os.getenv("PUSHOVER_TIMEOUT_SECONDS", "10")),
    "alert_worker_seconds": int(os.getenv("ALERT_WORKER_SECONDS", "15")),
    "alert_aqi_poll_seconds": int(os.getenv("ALERT_AQI_POLL_SECONDS", "300")),
    "alert_ha_poll_seconds": int(os.getenv("ALERT_HA_POLL_SECONDS", "60")),
    "alert_camera_poll_seconds": int(os.getenv("ALERT_CAMERA_POLL_SECONDS", "60")),
    "alert_internet_offline_seconds": int(os.getenv("ALERT_INTERNET_OFFLINE_SECONDS", "60")),
    "alert_ha_offline_seconds": int(os.getenv("ALERT_HA_OFFLINE_SECONDS", "300")),
    "alert_camera_offline_seconds": int(os.getenv("ALERT_CAMERA_OFFLINE_SECONDS", "600")),
    "alert_camera_battery_percent": int(os.getenv("ALERT_CAMERA_BATTERY_PERCENT", "20")),

    "wan_names": {
        "1": os.getenv("WAN1_NAME", "WAN 1"),
        "2": os.getenv("WAN2_NAME", "WAN 2"),
        "3": os.getenv("WAN3_NAME", "WAN 3"),
    },

    "wan_speeds": {
        "1": os.getenv("WAN1_SPEED", ""),
        "2": os.getenv("WAN2_SPEED", ""),
        "3": os.getenv("WAN3_SPEED", ""),
    },
}


def validate_config() -> None:
    """Reject contradictory thresholds before the application starts."""
    errors: list[str] = []

    if CONFIG["environment_temperature_critical_f"] < CONFIG["environment_temperature_warning_f"]:
        errors.append("ENVIRONMENT_TEMPERATURE_CRITICAL_F must be >= warning threshold")

    if CONFIG["environment_humidity_low_critical_percent"] > CONFIG["environment_humidity_low_warning_percent"]:
        errors.append("ENVIRONMENT_HUMIDITY_LOW_CRITICAL_PERCENT must be <= low warning threshold")

    if CONFIG["environment_humidity_high_critical_percent"] < CONFIG["environment_humidity_high_warning_percent"]:
        errors.append("ENVIRONMENT_HUMIDITY_HIGH_CRITICAL_PERCENT must be >= high warning threshold")

    if CONFIG["ring_critical_battery_percent"] > CONFIG["ring_low_battery_percent"]:
        errors.append("RING_CRITICAL_BATTERY_PERCENT must be <= RING_LOW_BATTERY_PERCENT")

    for key in (
        "poll_seconds",
        "home_assistant_timeout_seconds",
        "ring_timeout_seconds",
        "airnow_history_store_seconds",
        "airnow_history_retention_days",
        "airnow_trend_delta",
        "airnow_retry_attempts",
        "airnow_stale_seconds",
        "pushover_timeout_seconds",
        "alert_worker_seconds",
        "alert_aqi_poll_seconds",
        "alert_ha_poll_seconds",
        "alert_camera_poll_seconds",
        "alert_internet_offline_seconds",
        "alert_ha_offline_seconds",
        "alert_camera_offline_seconds",
    ):
        if CONFIG[key] <= 0:
            errors.append(f"{key} must be greater than zero")

    if errors:
        raise ValueError("Invalid RC-001 configuration: " + "; ".join(errors))


validate_config()
