from __future__ import annotations

import time
from typing import Any

from airnow import get_air_quality
from config import CONFIG
from database import (
    add_wan_durations,
    air_quality_trend,
    get_air_quality_history,
    log_air_quality,
    log_event,
    log_status,
)
from decision_engine import determine_lighting_status
from peplink import get_wan_status
from outdoor_weather import get_outdoor_weather
from release_info import get_release_metadata
import runtime_state
from temperature import get_humidity, get_temperature
from wled import PRESETS, set_status, trigger_air_quality_alert


def _simulated_wans(status: str) -> list[dict[str, Any]]:
    connected = status in {"normal", "failover"}
    return [
        {
            "id": "1",
            "name": "WAN 1",
            "connected": connected,
            "standby": False,
            "message": "Connected" if connected else "Down",
            "ip": "",
            "gateway": "",
            "speed": "",
        },
        {
            "id": "2",
            "name": "WAN 2",
            "connected": status == "normal",
            "standby": False,
            "message": "Connected" if status == "normal" else "Down",
            "ip": "",
            "gateway": "",
            "speed": "",
        },
        {
            "id": "3",
            "name": "USB T-Mobile",
            "connected": status == "tmobile",
            "standby": status != "tmobile",
            "message": "Connected" if status == "tmobile" else "Standby",
            "ip": "",
            "gateway": "",
            "speed": "",
        },
    ]


def _health_item(label: str, state: str, level: str) -> dict[str, str]:
    return {"label": label, "state": state, "level": level}


def _build_health(
    lighting_status: str,
    lighting_label: str,
    temperature: float | None,
    humidity: int | None,
    manual_override: bool,
    air_quality: dict[str, Any] | None = None,
) -> dict[str, dict[str, str]]:
    if lighting_status == "normal":
        internet = _health_item("Internet", "Healthy", "good")
    elif lighting_status == "failover":
        internet = _health_item("Internet", "Failover", "warning")
    elif lighting_status == "tmobile":
        internet = _health_item("Internet", "Backup Active", "info")
    else:
        internet = _health_item("Internet", "Offline", "critical")

    if temperature is None or humidity is None:
        environment = _health_item("Environment", "Unavailable", "warning")
    elif (
        temperature >= CONFIG["environment_temperature_critical_f"]
        or humidity >= CONFIG["environment_humidity_high_critical_percent"]
        or humidity <= CONFIG["environment_humidity_low_critical_percent"]
    ):
        environment = _health_item("Environment", "Critical", "critical")
    elif (
        temperature >= CONFIG["environment_temperature_warning_f"]
        or humidity >= CONFIG["environment_humidity_high_warning_percent"]
        or humidity <= CONFIG["environment_humidity_low_warning_percent"]
    ):
        environment = _health_item("Environment", "Watch", "warning")
    else:
        environment = _health_item("Environment", "Optimal", "good")

    # Outdoor air quality belongs to the environmental domain. Let it
    # override a less-severe cabinet state so the home card cannot report
    # "Optimal" while an outdoor smoke advisory is active.
    if air_quality and air_quality.get("available"):
        aqi = int(air_quality.get("aqi") or 0)
        if aqi >= 151:
            environment = _health_item(
                "Environment", "Air Quality Alert", "critical"
            )
        elif aqi >= 101 and environment["level"] != "critical":
            environment = _health_item(
                "Environment", "Smoke Present", "warning"
            )

    lighting_levels = {
        "normal": "good",
        "maintenance": "neutral",
        "network": "info",
        "failover": "warning",
        "tmobile": "info",
        "firmware": "info",
        "offline": "critical",
    }
    lighting = _health_item(
        "Lighting",
        lighting_label,
        lighting_levels.get(lighting_status, "neutral"),
    )

    automation = _health_item(
        "Automation",
        "Manual Override" if manual_override else "Active",
        "warning" if manual_override else "good",
    )

    return {
        "internet": internet,
        "environment": environment,
        "lighting": lighting,
        "automation": automation,
    }


def _system_information(
    temperature: float | None,
    humidity: int | None,
    speedtest: dict[str, Any],
    snmp_status: dict[str, Any],
    peplink_stale: bool,
) -> dict[str, dict[str, Any]]:
    release = get_release_metadata()
    return {
        "version": {
            "label": "Version",
            "value": f"RC-001 v{release.get('version', CONFIG['app_version'])}",
            "level": "neutral",
        },
        "application": {
            "label": "Application",
            "value": CONFIG["application_name"],
            "level": "neutral",
        },
        "database": {
            "label": "Database",
            "value": "Healthy",
            "level": "good",
        },
        "peplink": {
            "label": "Peplink",
            "value": "Telemetry Delayed" if peplink_stale else "Connected",
            "level": "warning" if peplink_stale else "good",
        },
        "wled": {
            "label": "WLED",
            "value": "Connected" if runtime_state.WLED_AVAILABLE else "Unavailable",
            "level": "good" if runtime_state.WLED_AVAILABLE else "warning",
        },
        "home_assistant": {
            "label": "Home Assistant",
            "value": "Connected" if temperature is not None or humidity is not None else "Unavailable",
            "level": "good" if temperature is not None or humidity is not None else "warning",
        },
        "snmp": {
            "label": "WAN Telemetry",
            "value": "Connected" if snmp_status.get("available") else "Unavailable",
            "level": "good" if snmp_status.get("available") else "warning",
        },
        "speedtest": {
            "label": "Speedtest",
            "value": "Ready" if speedtest.get("timestamp") else "Waiting",
            "level": "good" if speedtest.get("timestamp") else "warning",
        },
    }



def _process_air_quality(
    air_quality: dict[str, Any],
    lighting_status: str,
) -> None:
    if not air_quality.get("available"):
        return

    result = log_air_quality(air_quality)
    current_level = str(air_quality.get("level") or "unknown")
    previous_level = result.get("previous_level")
    runtime_state.LAST_AIR_QUALITY_LEVEL = current_level

    if not result.get("category_changed"):
        return

    log_event(
        "environment",
        (
            f"🌫 Outdoor air changed to {air_quality.get('category')}: "
            f"AQI {air_quality.get('aqi')} "
            f"({air_quality.get('pollutant') or 'AQI'})"
        ),
    )

    ranks = {
        "good": 0,
        "moderate": 1,
        "sensitive": 2,
        "unhealthy": 3,
        "very_unhealthy": 4,
        "hazardous": 5,
    }
    if ranks.get(current_level, -1) > ranks.get(str(previous_level), -1):
        trigger_air_quality_alert(current_level, lighting_status)

def collect_status(update_lights: bool = True) -> dict[str, Any]:
    now = time.time()
    now_int = int(now)

    if CONFIG["simulation_mode"]:
        lighting_status = CONFIG["simulation_status"]
        wans = _simulated_wans(lighting_status)
    else:
        # Preserve dashboard availability during a temporary router API
        # failure. Fresh calls still attempt automatic reauthentication first.
        wans = get_wan_status(allow_stale=True)
        lighting_status = determine_lighting_status(wans)

    peplink_stale = any(bool(wan.get("status_stale")) for wan in wans)
    peplink_error = next(
        (str(wan.get("status_error")) for wan in wans if wan.get("status_error")),
        None,
    )
    peplink_last_success = max(
        (int(wan.get("status_last_success") or 0) for wan in wans),
        default=0,
    )

    wans = add_wan_durations(wans, now_int)

    snmp_status = runtime_state.get_snmp_status()
    wan_telemetry = snmp_status.get("wans", {})
    for wan in wans:
        telemetry = wan_telemetry.get(str(wan.get("id")), {})
        wan["download_mbps"] = telemetry.get("download_mbps")
        wan["upload_mbps"] = telemetry.get("upload_mbps")
        wan["traffic_share_percent"] = telemetry.get("traffic_share_percent")
        wan["telemetry_available"] = bool(snmp_status.get("available") and telemetry)

    if runtime_state.MANUAL_OVERRIDE_STATUS and now < runtime_state.MANUAL_OVERRIDE_UNTIL:
        lighting_status = runtime_state.MANUAL_OVERRIDE_STATUS
    elif runtime_state.MANUAL_OVERRIDE_STATUS:
        runtime_state.MANUAL_OVERRIDE_STATUS = None
        runtime_state.MANUAL_OVERRIDE_UNTIL = 0

    if update_lights:
        try:
            set_status(lighting_status)
            runtime_state.WLED_AVAILABLE = True
        except Exception as exc:
            runtime_state.WLED_AVAILABLE = False
            print(f"WLED update failed: {exc}")

    temperature = get_temperature()
    humidity = get_humidity()
    speedtest = runtime_state.get_speedtest()

    air_quality = get_air_quality()
    outdoor_weather = get_outdoor_weather()
    _process_air_quality(air_quality, lighting_status)
    air_quality_history = get_air_quality_history(
        CONFIG["airnow_history_hours"]
    )
    air_quality["history"] = air_quality_history
    air_quality["trend"] = air_quality_trend(air_quality_history)
    lighting_label = PRESETS[lighting_status]["label"]
    manual_override = runtime_state.MANUAL_OVERRIDE_STATUS is not None

    status = {
        "timestamp": now_int,
        "lighting_status": lighting_status,
        "lighting_label": lighting_label,
        "wans": wans,
        "temperature": temperature,
        "humidity": humidity,
        "air_quality": air_quality,
        "outdoor_weather": outdoor_weather,
        "simulation_mode": CONFIG["simulation_mode"],
        "manual_override": manual_override,
        "uptime_seconds": int(now - runtime_state.APP_START_TIME),
        "speedtest": speedtest,
        "snmp": snmp_status,
        "peplink": {
            "available": not peplink_stale,
            "stale": peplink_stale,
            "last_success": peplink_last_success,
            "error": peplink_error,
        },
        "health": _build_health(
            lighting_status,
            lighting_label,
            temperature,
            humidity,
            manual_override,
            air_quality,
        ),
        "system_information": _system_information(
            temperature,
            humidity,
            speedtest,
            snmp_status,
            peplink_stale,
        ),
    }

    log_status(status)
    return status
