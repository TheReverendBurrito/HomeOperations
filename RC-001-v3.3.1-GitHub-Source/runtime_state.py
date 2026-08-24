from __future__ import annotations

import threading
import time
from typing import Any

APP_START_TIME = time.time()

LAST_LOGGED_STATUS: str | None = None
LAST_LIGHT_STATUS: str | None = None
MANUAL_OVERRIDE_STATUS: str | None = None
MANUAL_OVERRIDE_UNTIL: float = 0
WLED_AVAILABLE: bool = False
LAST_AIR_QUALITY_LEVEL: str | None = None

_SPEEDTEST_LOCK = threading.Lock()
_LAST_SPEEDTEST: dict[str, Any] = {
    "download": None,
    "upload": None,
    "ping": None,
    "jitter": None,
    "server": None,
    "server_location": None,
    "result_url": None,
    "timestamp": 0,
}


def get_speedtest() -> dict[str, Any]:
    with _SPEEDTEST_LOCK:
        return dict(_LAST_SPEEDTEST)


def set_speedtest(value: dict[str, Any]) -> None:
    with _SPEEDTEST_LOCK:
        _LAST_SPEEDTEST.clear()
        _LAST_SPEEDTEST.update(value)


_SNMP_LOCK = threading.Lock()
_SNMP_STATUS: dict[str, Any] = {
    "available": False,
    "last_success": 0,
    "error": None,
    "wans": {},
}


def get_snmp_status() -> dict[str, Any]:
    with _SNMP_LOCK:
        return {
            "available": bool(_SNMP_STATUS.get("available")),
            "last_success": int(_SNMP_STATUS.get("last_success", 0)),
            "error": _SNMP_STATUS.get("error"),
            "wans": {
                str(key): dict(value)
                for key, value in dict(_SNMP_STATUS.get("wans", {})).items()
            },
        }


def set_snmp_status(value: dict[str, Any]) -> None:
    with _SNMP_LOCK:
        _SNMP_STATUS.clear()
        _SNMP_STATUS.update(value)
