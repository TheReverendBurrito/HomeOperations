from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from airnow import get_air_quality
from config import BASE_DIR, CONFIG
from database import DB_PATH, log_event
from home_assistant import check_health
from peplink import get_wan_status
from pushover_service import is_configured, send_notification_detailed
from ring_service import collect_ring_status


LOGGER = logging.getLogger(__name__)
WATCHDOG_STATE_FILE = Path(BASE_DIR) / "data" / "watchdog_state.json"
_WORKER_LOCK = threading.Lock()
_WORKER_STARTED = False
_WORKER_LAST_CYCLE = 0

_ALERT_COLUMNS = (
    "current_state", "condition_since", "consecutive_count",
    "last_observation_key", "active", "last_notified", "updated_at",
    "delivery_status", "pending_title", "pending_message", "pending_priority",
    "retry_count", "next_retry_at", "last_delivery_error",
    "last_delivered_at", "last_delivery_request",
)


def _default_state() -> dict[str, Any]:
    return {
        "current_state": "normal", "condition_since": None,
        "consecutive_count": 0, "last_observation_key": None,
        "active": False, "last_notified": None, "updated_at": 0,
        "delivery_status": "none", "pending_title": None,
        "pending_message": None, "pending_priority": None,
        "retry_count": 0, "next_retry_at": None,
        "last_delivery_error": None, "last_delivered_at": None,
        "last_delivery_request": None,
    }


def _row(alert_id: str) -> dict[str, Any]:
    with sqlite3.connect(DB_PATH) as conn:
        record = conn.execute(
            f"SELECT {', '.join(_ALERT_COLUMNS)} FROM alert_state WHERE alert_id = ?",
            (alert_id,),
        ).fetchone()
    if not record:
        return _default_state()
    state = dict(zip(_ALERT_COLUMNS, record))
    state["active"] = bool(state["active"])
    return state


def _save(alert_id: str, state: dict[str, Any]) -> None:
    values = [state.get(column) for column in _ALERT_COLUMNS]
    values[_ALERT_COLUMNS.index("active")] = 1 if state.get("active") else 0
    placeholders = ", ".join("?" for _ in range(len(_ALERT_COLUMNS) + 1))
    updates = ", ".join(f"{column}=excluded.{column}" for column in _ALERT_COLUMNS)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            f"""INSERT INTO alert_state (alert_id, {', '.join(_ALERT_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT(alert_id) DO UPDATE SET {updates}""",
            [alert_id, *values],
        )
        conn.commit()


def _retry_delay(retry_count: int) -> int:
    schedule = (60, 300, 900, 1800, 3600)
    return schedule[min(max(0, retry_count - 1), len(schedule) - 1)]


def _clear_pending(state: dict[str, Any]) -> None:
    state.update(
        pending_title=None, pending_message=None, pending_priority=None,
        retry_count=0, next_retry_at=None,
    )


def _attempt_delivery(alert_id: str, state: dict[str, Any]) -> bool:
    title = state.get("pending_title")
    message = state.get("pending_message")
    if not title or not message:
        return False
    now = int(time.time())
    result = send_notification_detailed(
        str(title), str(message), priority=int(state.get("pending_priority") or 0)
    )
    if result["ok"]:
        retried = int(state.get("retry_count") or 0) > 0
        state.update(
            delivery_status="delivered", last_delivery_error=None,
            last_delivered_at=now, last_delivery_request=result.get("request"),
            last_notified=now,
        )
        _clear_pending(state)
        if retried:
            log_event("alert", f"🟢 Delayed alert delivered — {title}")
        return True

    retry_count = int(state.get("retry_count") or 0) + 1
    state.update(
        delivery_status="pending", retry_count=retry_count,
        next_retry_at=now + _retry_delay(retry_count),
        last_delivery_error=result.get("error") or "Unknown delivery failure",
    )
    LOGGER.warning(
        "Alert %s delivery attempt %s failed: %s",
        alert_id, retry_count, state["last_delivery_error"],
    )
    return False


def _queue_notification(
    alert_id: str,
    state: dict[str, Any],
    title: str,
    message: str,
    *,
    priority: int = 0,
) -> None:
    now = int(time.time())
    state.update(
        delivery_status="pending", pending_title=title,
        pending_message=message, pending_priority=priority,
        retry_count=0, next_retry_at=now, last_delivery_error=None,
        last_notified=now,
    )
    log_event("alert", f"🔔 {title}: {message}")
    _attempt_delivery(alert_id, state)


def _cancel_undelivered(state: dict[str, Any]) -> bool:
    was_pending = state.get("delivery_status") == "pending"
    if was_pending:
        state["delivery_status"] = "cancelled"
        state["last_delivery_error"] = None
        _clear_pending(state)
    return was_pending


def _retry_pending_notifications() -> None:
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        alert_ids = [
            row[0] for row in conn.execute(
                """SELECT alert_id FROM alert_state
                   WHERE delivery_status = 'pending'
                     AND next_retry_at IS NOT NULL AND next_retry_at <= ?""",
                (now,),
            ).fetchall()
        ]
    for alert_id in alert_ids:
        state = _row(alert_id)
        _attempt_delivery(alert_id, state)
        state["updated_at"] = now
        _save(alert_id, state)


def _duration_alert(
    alert_id: str,
    condition: bool,
    delay_seconds: int,
    title: str,
    message: str,
    recovery_message: str,
    *,
    priority: int = 0,
) -> None:
    now = int(time.time())
    state = _row(alert_id)
    if condition:
        if state.get("condition_since") is None:
            state["condition_since"] = now
        state["current_state"] = "pending" if not state["active"] else "active"
        if not state["active"] and now - int(state["condition_since"]) >= delay_seconds:
            state["active"] = True
            state["current_state"] = "active"
            _queue_notification(alert_id, state, title, message, priority=priority)
    else:
        if state["active"]:
            delivered = state.get("delivery_status") == "delivered"
            _cancel_undelivered(state)
            if delivered:
                _queue_notification(
                    alert_id, state, f"{title} Cleared", recovery_message
                )
        state.update(
            current_state="normal", condition_since=None,
            consecutive_count=0, active=False,
        )
    state["updated_at"] = now
    _save(alert_id, state)


def _evaluate_aqi() -> None:
    observation = get_air_quality(force_refresh=True)
    if (
        not observation.get("available")
        or not observation.get("is_fresh", True)
        or observation.get("aqi") is None
    ):
        return
    now = int(time.time())
    aqi = int(observation["aqi"])
    pollutant = observation.get("pollutant") or "AQI"
    observation_key = str(observation.get("fetch_id") or observation.get("updated_at") or now)
    target = "critical" if aqi >= 201 else "advisory" if aqi >= 151 else "normal"
    state = _row("environment:aqi")
    if state.get("last_observation_key") == observation_key:
        return

    previous_target = state.get("current_state")
    if target == previous_target:
        state["consecutive_count"] = int(state.get("consecutive_count") or 0) + 1
    else:
        state["current_state"] = target
        state["condition_since"] = now
        state["consecutive_count"] = 1
        if target == "critical" or (target == "advisory" and previous_target == "normal"):
            state["active"] = False
    state["last_observation_key"] = observation_key
    state["updated_at"] = now

    if target in {"advisory", "critical"} and state["consecutive_count"] >= 2:
        if not state["active"]:
            title = "RC-001 — Extreme AQI" if target == "critical" else "RC-001 — Unhealthy AQI"
            category = observation.get("category") or "Unhealthy"
            state["active"] = True
            _queue_notification(
                "environment:aqi", state, title,
                f"{pollutant} AQI {aqi} — {category}. Two consecutive readings confirmed.",
                priority=1 if target == "critical" else 0,
            )
    elif target == "normal" and state["consecutive_count"] >= 2 and state["active"]:
        delivered = state.get("delivery_status") == "delivered"
        _cancel_undelivered(state)
        if delivered:
            _queue_notification(
                "environment:aqi", state, "RC-001 — AQI Improved",
                f"{pollutant} AQI {aqi}. Air quality is below the alert threshold.",
            )
        state["active"] = False
    _save("environment:aqi", state)


def _evaluate_internet() -> None:
    try:
        wans = get_wan_status()
        offline = not any(bool(wan.get("connected")) for wan in wans)
    except Exception as exc:
        LOGGER.warning("WAN alert check failed: %s", exc)
        return
    seconds = CONFIG["alert_internet_offline_seconds"]
    _duration_alert(
        "network:internet", offline, seconds,
        "RC-001 — Internet Offline",
        f"No usable WAN has been available for {seconds} seconds.",
        "At least one usable WAN is available again.", priority=1,
    )


def _evaluate_home_assistant() -> bool:
    available, error = check_health(timeout=CONFIG["home_assistant_timeout_seconds"])
    seconds = CONFIG["alert_ha_offline_seconds"]
    _duration_alert(
        "infrastructure:home_assistant", not available, seconds,
        "RC-001 — Home Assistant Offline",
        f"Home Assistant has been unreachable for {max(1, seconds // 60)} minutes.",
        "Home Assistant connectivity has been restored.", priority=1,
    )
    if error:
        LOGGER.debug("Home Assistant health check: %s", error)
    return available


def _evaluate_cameras(ha_available: bool) -> None:
    if not ha_available:
        return
    payload = collect_ring_status(log_changes=False)
    if not payload.get("available"):
        return
    now = int(time.time())
    threshold = CONFIG["alert_camera_battery_percent"]
    seconds = CONFIG["alert_camera_offline_seconds"]
    for camera in payload.get("cameras", []):
        camera_id = str(camera.get("id"))
        name = str(camera.get("name") or camera_id)
        _duration_alert(
            f"security:camera:{camera_id}:offline",
            not bool(camera.get("available")), seconds,
            f"RC-001 — {name} Camera Offline",
            f"{name} has been unavailable for {max(1, seconds // 60)} minutes.",
            f"{name} camera connectivity has been restored.",
        )

        battery = camera.get("battery_percent")
        alert_id = f"security:camera:{camera_id}:battery_alert"
        state = _row(alert_id)
        is_low = battery is not None and int(battery) <= threshold
        delivery_due = (
            state.get("delivery_status") != "pending"
            and (
                not state["active"]
                or not state.get("last_delivered_at")
                or now - int(state["last_delivered_at"]) >= 86400
            )
        )
        if is_low and delivery_due:
            state["active"] = True
            state["current_state"] = "low"
            _queue_notification(
                alert_id, state, f"RC-001 — {name} Battery Low",
                f"{name} camera battery is {int(battery)}%.",
            )
        elif battery is not None and not is_low and state["active"]:
            delivered = state.get("delivery_status") == "delivered"
            _cancel_undelivered(state)
            if delivered:
                _queue_notification(
                    alert_id, state, f"RC-001 — {name} Battery Recovered",
                    f"{name} camera battery is now {int(battery)}%.",
                )
            state.update(active=False, current_state="normal")
        state["updated_at"] = now
        _save(alert_id, state)


def _watchdog_snapshot(now: int) -> dict[str, Any]:
    try:
        payload = json.loads(WATCHDOG_STATE_FILE.read_text(encoding="utf-8"))
        updated_at = int(payload.get("updated_at") or 0)
        return {
            "healthy": bool(updated_at and now - updated_at <= 90),
            "updated_at": updated_at or None,
            "age_seconds": max(0, now - updated_at) if updated_at else None,
        }
    except (OSError, ValueError, TypeError):
        return {"healthy": False, "updated_at": None, "age_seconds": None}


def get_alert_snapshot() -> dict[str, Any]:
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """SELECT alert_id, current_state, condition_since, active,
                      last_notified, updated_at, delivery_status, retry_count,
                      next_retry_at, last_delivery_error, last_delivered_at,
                      last_delivery_request
               FROM alert_state ORDER BY alert_id"""
        ).fetchall()
    alerts = [
        {
            "alert_id": row[0], "state": row[1], "condition_since": row[2],
            "active": bool(row[3]), "last_notified": row[4], "updated_at": row[5],
            "delivery_status": row[6], "retry_count": row[7],
            "next_retry_at": row[8], "last_delivery_error": row[9],
            "last_delivered_at": row[10], "last_delivery_request": row[11],
        }
        for row in rows
    ]
    delivery_pending = sum(item["delivery_status"] == "pending" for item in alerts)
    active_count = sum(item["active"] for item in alerts)
    condition_pending = sum(item["state"] == "pending" for item in alerts)
    delivered_times = [item["last_delivered_at"] for item in alerts if item["last_delivered_at"]]
    errors = [item["last_delivery_error"] for item in alerts if item["last_delivery_error"]]
    configured = is_configured()
    worker_healthy = bool(_WORKER_STARTED and now - _WORKER_LAST_CYCLE <= 180)
    if not configured:
        delivery_health = "unconfigured"
    elif delivery_pending:
        delivery_health = "retrying"
    elif errors:
        delivery_health = "degraded"
    else:
        delivery_health = "healthy"
    return {
        "enabled": bool(CONFIG.get("pushover_enabled")),
        "configured": configured,
        "worker": {"healthy": worker_healthy, "last_cycle": _WORKER_LAST_CYCLE or None},
        "watchdog": _watchdog_snapshot(now),
        "summary": {
            "active": active_count,
            "pending_conditions": condition_pending,
            "pending_deliveries": delivery_pending,
            "delivery_health": delivery_health,
            "last_delivered_at": max(delivered_times) if delivered_times else None,
            "last_delivery_error": errors[-1] if errors else None,
        },
        "alerts": alerts,
        "updated_at": now,
    }


def _worker() -> None:
    global _WORKER_LAST_CYCLE
    next_aqi = next_ha = next_cameras = 0.0
    ha_available = False
    while True:
        now = time.monotonic()
        try:
            _WORKER_LAST_CYCLE = int(time.time())
            _retry_pending_notifications()
            _evaluate_internet()
            if now >= next_ha:
                ha_available = _evaluate_home_assistant()
                next_ha = now + CONFIG["alert_ha_poll_seconds"]
            if now >= next_cameras:
                _evaluate_cameras(ha_available)
                next_cameras = now + CONFIG["alert_camera_poll_seconds"]
            if now >= next_aqi:
                _evaluate_aqi()
                next_aqi = now + CONFIG["alert_aqi_poll_seconds"]
        except Exception:
            LOGGER.exception("RC-001 alert worker cycle failed")
        time.sleep(CONFIG["alert_worker_seconds"])


def start_alert_worker() -> None:
    global _WORKER_STARTED
    with _WORKER_LOCK:
        if _WORKER_STARTED:
            return
        _WORKER_STARTED = True
        threading.Thread(target=_worker, name="rc001-alerts", daemon=True).start()
