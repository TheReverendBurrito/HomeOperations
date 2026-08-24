from __future__ import annotations

import requests
import threading
import time

from config import CONFIG
import runtime_state


PRESETS = {
    "normal": {
        "label": "Normal",
        "preset": 1,
    },
    "maintenance": {
        "label": "Maintenance",
        "preset": 2,
    },
    "firmware": {
        "label": "Firmware Update",
        "preset": 3,
    },
    "network": {
        "label": "Network",
        "preset": 4,
    },
    "failover": {
        "label": "WAN Failover",
        "preset": 5,
    },
    "tmobile": {
        "label": "T-Mobile Active",
        "preset": 6,
    },
    "offline": {
        "label": "Critical",
        "preset": 7,
    },
}


def set_status(status: str, force: bool = False) -> None:
    """
    Apply the WLED preset associated with an RC-001 lighting status.

    Args:
        status:
            RC-001 lighting status such as "normal", "maintenance",
            "network", "failover", "tmobile", "firmware", or "offline".

        force:
            When True, resend the preset even if RC-001 believes the
            same lighting status is already active.

    Raises:
        ValueError:
            If the requested lighting status is not defined.

        requests.RequestException:
            If WLED cannot be reached or returns an HTTP error.
    """
    if status not in PRESETS:
        raise ValueError(f"Unknown lighting status: {status}")

    if not force and status == runtime_state.LAST_LIGHT_STATUS:
        return

    base_url = str(CONFIG["wled_base_url"]).rstrip("/")
    preset = PRESETS[status]["preset"]

    response = requests.post(
        f"{base_url}/json/state",
        json={
            "on": True,
            "ps": preset,
        },
        timeout=5,
    )

    response.raise_for_status()

    runtime_state.LAST_LIGHT_STATUS = status

_AQI_ALERT_LOCK = threading.Lock()
_AQI_ALERT_ACTIVE = False


def trigger_air_quality_alert(level: str, restore_status: str) -> bool:
    global _AQI_ALERT_ACTIVE

    if not CONFIG["airnow_led_alerts"]:
        return False
    if level not in {"sensitive", "unhealthy", "very_unhealthy", "hazardous"}:
        return False
    if restore_status not in PRESETS:
        restore_status = "normal"

    colors = {
        "sensitive": [255, 126, 0],
        "unhealthy": [255, 0, 0],
        "very_unhealthy": [143, 63, 151],
        "hazardous": [126, 0, 35],
    }

    with _AQI_ALERT_LOCK:
        if _AQI_ALERT_ACTIVE:
            return False
        _AQI_ALERT_ACTIVE = True

    def worker() -> None:
        global _AQI_ALERT_ACTIVE
        base_url = str(CONFIG["wled_base_url"]).rstrip("/")
        try:
            response = requests.post(
                f"{base_url}/json/state",
                json={
                    "on": True,
                    "transition": 4,
                    "seg": [{
                        "fx": 2,
                        "sx": 120,
                        "ix": 170,
                        "col": [colors[level]],
                    }],
                },
                timeout=5,
            )
            response.raise_for_status()
            time.sleep(max(3, CONFIG["airnow_led_alert_seconds"]))
            set_status(restore_status, force=True)
        except Exception as exc:
            print(f"AQI WLED alert failed: {exc}")
        finally:
            with _AQI_ALERT_LOCK:
                _AQI_ALERT_ACTIVE = False

    threading.Thread(
        target=worker,
        name="rc001-aqi-alert",
        daemon=True,
    ).start()
    return True
