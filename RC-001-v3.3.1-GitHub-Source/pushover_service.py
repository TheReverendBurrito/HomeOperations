from __future__ import annotations

import logging
from typing import Any

import requests

from config import CONFIG


LOGGER = logging.getLogger(__name__)
PUSHOVER_MESSAGES_URL = "https://api.pushover.net/1/messages.json"


def is_configured() -> bool:
    return bool(
        CONFIG.get("pushover_enabled")
        and CONFIG.get("pushover_user_key")
        and CONFIG.get("pushover_api_token")
    )


def send_notification(
    title: str,
    message: str,
    *,
    priority: int = 0,
    sound: str | None = None,
) -> tuple[bool, str | None]:
    """Send one Pushover notification; never expose credentials in errors."""
    result = send_notification_detailed(
        title, message, priority=priority, sound=sound
    )
    return bool(result["ok"]), result.get("error")


def send_notification_detailed(
    title: str,
    message: str,
    *,
    priority: int = 0,
    sound: str | None = None,
) -> dict[str, Any]:
    """Send a notification and return non-secret delivery telemetry."""
    if not is_configured():
        return {"ok": False, "error": "Pushover is not configured", "request": None}

    payload: dict[str, Any] = {
        "token": CONFIG["pushover_api_token"],
        "user": CONFIG["pushover_user_key"],
        "title": title[:250],
        "message": message[:1024],
        "priority": max(-2, min(1, int(priority))),
    }
    if CONFIG.get("pushover_device"):
        payload["device"] = CONFIG["pushover_device"]
    if CONFIG.get("pushover_dashboard_url"):
        payload["url"] = CONFIG["pushover_dashboard_url"]
        payload["url_title"] = "Open Home Operations Center"
    if sound:
        payload["sound"] = sound

    try:
        response = requests.post(
            PUSHOVER_MESSAGES_URL,
            data=payload,
            timeout=CONFIG["pushover_timeout_seconds"],
            headers={"User-Agent": "RC-001/3.1"},
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            return {
                "ok": False,
                "error": "Pushover returned an invalid response",
                "request": None,
            }
        if int(body.get("status", 0)) != 1:
            return {
                "ok": False,
                "error": "Pushover rejected the notification",
                "request": body.get("request"),
            }
        return {"ok": True, "error": None, "request": body.get("request")}
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("Pushover delivery failed: %s", exc)
        return {
            "ok": False,
            "error": f"Pushover delivery failed: {type(exc).__name__}",
            "request": None,
        }
