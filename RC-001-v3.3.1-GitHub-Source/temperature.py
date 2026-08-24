from __future__ import annotations

from config import CONFIG
from home_assistant import HomeAssistantError, get_state, numeric_value


def _get_sensor_value(entity: str | None) -> tuple[float | None, str]:
    """Read one numeric Home Assistant sensor without surfacing outages.

    Environmental telemetry is optional dashboard data. A missing entity,
    unavailable state, invalid numeric value, or Home Assistant request failure
    therefore returns ``(None, "")`` and lets the status service report the
    environment as unavailable.
    """
    try:
        state = get_state(entity)
    except HomeAssistantError:
        return None, ""

    value = numeric_value(state)
    if value is None:
        return None, ""

    attributes = (state or {}).get("attributes") or {}
    unit = str(attributes.get("unit_of_measurement", "")).strip()
    return value, unit


def get_temperature() -> float | None:
    """Return cabinet temperature in degrees Fahrenheit."""
    value, unit = _get_sensor_value(CONFIG.get("temperature_entity"))
    if value is None:
        return None

    if unit in {"°C", "C"}:
        value = value * 9 / 5 + 32

    return round(value, 1)


def get_humidity() -> int | None:
    """Return cabinet relative humidity as a whole-number percentage."""
    value, _ = _get_sensor_value(CONFIG.get("humidity_entity"))
    return None if value is None else round(value)
