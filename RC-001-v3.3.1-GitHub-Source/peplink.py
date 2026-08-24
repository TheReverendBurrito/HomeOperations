from __future__ import annotations

from copy import deepcopy
import logging
import threading
import time
from typing import Any

import requests
import urllib3

from config import CONFIG

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOGGER = logging.getLogger(__name__)
SESSION = requests.Session()
_SESSION_LOCK = threading.RLock()
_LAST_WAN_STATUS: list[dict[str, Any]] = []
_LAST_WAN_SUCCESS = 0


class PeplinkError(RuntimeError):
    """Base error raised for Peplink authentication and API failures."""


class PeplinkUnauthorizedError(PeplinkError):
    """Raised when Peplink rejects the current authenticated session."""


def _response_data(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise PeplinkError(
            f"Peplink returned an invalid JSON response (HTTP {response.status_code})"
        ) from exc

    if not isinstance(data, dict):
        raise PeplinkError("Peplink returned an unexpected response payload")
    return data


def _is_unauthorized(response: requests.Response, data: dict[str, Any]) -> bool:
    try:
        api_code = int(data.get("code", 0))
    except (TypeError, ValueError):
        api_code = 0
    return response.status_code == 401 or api_code == 401


def _login_locked() -> None:
    response = SESSION.post(
        f"{CONFIG['peplink_base_url']}/api/login",
        json={
            "username": CONFIG["peplink_username"],
            "password": CONFIG["peplink_password"],
        },
        verify=False,
        timeout=10,
    )
    if response.status_code == 401:
        raise PeplinkUnauthorizedError("Peplink login was unauthorized")
    data = _response_data(response)
    if _is_unauthorized(response, data):
        raise PeplinkUnauthorizedError("Peplink login was unauthorized")
    response.raise_for_status()
    if data.get("stat") != "ok":
        raise PeplinkError(f"Peplink login failed: {data}")


def login() -> None:
    if not CONFIG["peplink_password"]:
        raise PeplinkError("PEPLINK_PASSWORD is not set")

    with _SESSION_LOCK:
        _login_locked()


def _get_locked(
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = SESSION.get(
        f"{CONFIG['peplink_base_url']}{path}",
        params=params,
        verify=False,
        timeout=10,
    )
    if response.status_code == 401:
        raise PeplinkUnauthorizedError("Peplink session is unauthorized")
    data = _response_data(response)
    if _is_unauthorized(response, data):
        raise PeplinkUnauthorizedError("Peplink session is unauthorized")
    response.raise_for_status()
    if data.get("stat") != "ok":
        raise PeplinkError(f"Peplink API error: {data}")

    payload = data.get("response")
    if not isinstance(payload, dict):
        raise PeplinkError("Peplink API response payload is missing")
    return payload


def get(
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get a Peplink API resource, renewing an expired session once."""
    with _SESSION_LOCK:
        try:
            return _get_locked(path, params=params)
        except PeplinkUnauthorizedError:
            # The dashboard and alert worker share this lock. Only the first
            # caller that observes an expired session performs the login;
            # waiting callers reuse the renewed session.
            _login_locked()
            LOGGER.warning("Peplink session expired; authentication renewed")
            return _get_locked(path, params=params)


def get_wan_status(*, allow_stale: bool = False) -> list[dict[str, Any]]:
    global _LAST_WAN_STATUS, _LAST_WAN_SUCCESS

    try:
        response = get("/api/status.wan.connection")
    except Exception as exc:
        with _SESSION_LOCK:
            if not allow_stale or not _LAST_WAN_STATUS:
                raise
            cached = deepcopy(_LAST_WAN_STATUS)
            last_success = _LAST_WAN_SUCCESS
        for wan in cached:
            wan["status_stale"] = True
            wan["status_error"] = str(exc)
            wan["status_last_success"] = last_success
        return cached

    wans: list[dict[str, Any]] = []

    for raw_id in response.get("order", []):
        wan_id = str(raw_id)
        info = response.get(wan_id, {})
        if not info.get("enable", False):
            continue

        name = CONFIG["wan_names"].get(wan_id, info.get("name", f"WAN {wan_id}"))
        status_led = str(info.get("statusLed", "")).lower()
        raw_message = str(info.get("message", ""))
        connected = status_led == "green"
        standby = status_led == "yellow" or "standby" in raw_message.lower()

        if connected:
            message = "Connected"
        elif standby:
            message = "Standby"
        else:
            message = raw_message or "Down"

        wans.append(
            {
                "id": wan_id,
                "name": name,
                "connected": connected,
                "standby": standby,
                "status_led": status_led,
                "message": message,
                "ip": info.get("ip", ""),
                "gateway": info.get("gateway", ""),
                "speed": CONFIG["wan_speeds"].get(wan_id, ""),
                "status_stale": False,
                "status_error": None,
                "status_last_success": int(time.time()),
            }
        )

    with _SESSION_LOCK:
        _LAST_WAN_STATUS = deepcopy(wans)
        _LAST_WAN_SUCCESS = int(time.time())
    return deepcopy(wans)
