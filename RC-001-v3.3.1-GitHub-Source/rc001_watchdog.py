from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

from config import BASE_DIR
from pushover_service import send_notification


LOGGER = logging.getLogger("rc001-watchdog")
HEALTH_URL = "http://127.0.0.1:5050/api/build"
CHECK_SECONDS = 30
FAILURE_SECONDS = 180
STATE_FILE = BASE_DIR / "data" / "watchdog_state.json"


def _load() -> dict:
    try:
        value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(STATE_FILE)


def _healthy() -> bool:
    try:
        response = requests.get(HEALTH_URL, timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False


def main() -> None:
    state = _load()
    failure_since = state.get("failure_since")
    alerted = bool(state.get("alerted", False))
    while True:
        now = int(time.time())
        if _healthy():
            if alerted:
                send_notification(
                    "RC-001 — Service Restored",
                    "The Home Operations Center dashboard is responding again.",
                    priority=1,
                )
            failure_since = None
            alerted = False
        else:
            if failure_since is None:
                failure_since = now
            if not alerted and now - int(failure_since) >= FAILURE_SECONDS:
                ok, error = send_notification(
                    "RC-001 — Service Down",
                    "The Home Operations Center dashboard has failed its health check for 3 minutes.",
                    priority=1,
                )
                if ok:
                    alerted = True
                elif error:
                    LOGGER.warning("Watchdog notification failed: %s", error)
        state = {
            "failure_since": failure_since,
            "alerted": alerted,
            "updated_at": now,
        }
        _save(state)
        time.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
