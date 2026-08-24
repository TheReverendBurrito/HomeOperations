from __future__ import annotations

import time
from typing import Any

from config import CONFIG
from event_engine import StateTransition, apply_transitions
from home_assistant import (
    boolean_attribute,
    boolean_state,
    get_states_snapshot,
    integer_value,
    is_available,
    timestamp_value,
)

def _battery_band(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value < CONFIG["ring_critical_battery_percent"]:
        return "critical"
    if value < CONFIG["ring_low_battery_percent"]:
        return "low"
    return "normal"


def _major_security_transitions(
    cameras: list[dict[str, Any]],
    integration_available: bool,
) -> list[StateTransition]:
    transitions: list[StateTransition] = []

    transitions.append(
        StateTransition(
            object_id="security:ring_integration",
            category="security",
            state="available" if integration_available else "unavailable",
            event_id="SEC-001" if not integration_available else "SEC-002",
            severity="critical" if not integration_available else "recovery",
            message=(
                "🔴 Home Assistant / Ring integration unavailable"
                if not integration_available
                else "🟢 Home Assistant / Ring integration restored"
            ),
            emit_from=("available",) if not integration_available else ("unavailable",),
        )
    )

    # When the integration itself is unavailable, camera states are unknown.
    # Do not incorrectly declare every physical camera offline.
    if not integration_available:
        return transitions

    for camera in cameras:
        camera_id = camera["id"]
        camera_name = camera["name"]

        online = bool(camera.get("available"))
        transitions.append(
            StateTransition(
                object_id=f"security:camera:{camera_id}:availability",
                category="security",
                state="online" if online else "offline",
                event_id="SEC-101" if not online else "SEC-102",
                severity="critical" if not online else "recovery",
                message=(
                    f"🔴 {camera_name} camera offline"
                    if not online
                    else f"🟢 {camera_name} camera restored"
                ),
                emit_from=("online",) if not online else ("offline",),
            )
        )

        battery = camera.get("battery_percent")
        band = _battery_band(battery)
        if band == "critical":
            battery_message = f"🔴 {camera_name} camera battery critical — {battery}%"
            event_id, severity = "SEC-201", "critical"
        elif band == "low":
            battery_message = f"🟡 {camera_name} camera battery low — {battery}%"
            event_id, severity = "SEC-202", "warning"
        elif band == "normal":
            battery_message = f"🟢 {camera_name} camera battery recovered — {battery}%"
            event_id, severity = "SEC-203", "recovery"
        else:
            battery_message = None
            event_id, severity = None, None

        transitions.append(
            StateTransition(
                object_id=f"security:camera:{camera_id}:battery",
                category="security",
                state=band,
                event_id=event_id,
                severity=severity,
                message=battery_message,
                emit_from=("normal", "low") if band == "critical"
                else ("normal",) if band == "low"
                else ("low", "critical") if band == "normal"
                else None,
            )
        )

        motion = camera.get("motion_enabled")
        motion_state = "enabled" if motion is True else "disabled" if motion is False else "unknown"
        transitions.append(
            StateTransition(
                object_id=f"security:camera:{camera_id}:motion",
                category="security",
                state=motion_state,
                event_id="SEC-301" if motion is False else "SEC-302" if motion is True else None,
                severity="warning" if motion is False else "recovery" if motion is True else None,
                message=(
                    f"🟡 Motion detection disabled — {camera_name}"
                    if motion is False
                    else f"🟢 Motion detection restored — {camera_name}"
                    if motion is True
                    else None
                ),
                emit_from=("enabled",) if motion is False else ("disabled",) if motion is True else None,
            )
        )

    return transitions


def collect_ring_status(log_changes: bool = True) -> dict[str, Any]:
    cameras: list[dict[str, Any]] = []
    errors: list[str] = []

    snapshot_error: Exception | None = None
    try:
        states = get_states_snapshot(timeout=CONFIG["ring_timeout_seconds"])
    except Exception as exc:
        states = {}
        snapshot_error = exc

    for definition in CONFIG["ring_cameras"]:
        try:
            if snapshot_error is not None:
                raise snapshot_error
            camera_state = states.get(definition["camera_entity"])
            battery_state = states.get(definition.get("battery_entity"))
            activity_state = states.get(definition.get("last_activity_entity"))
            motion_state = states.get(definition.get("motion_detection_entity"))
            light_state = states.get(definition.get("light_entity"))
            siren_state = states.get(definition.get("siren_entity"))

            battery = integer_value(battery_state)
            activity_raw, activity_epoch, activity_attrs = timestamp_value(activity_state)
            available = is_available(camera_state)

            # Prefer the dedicated motion-detection switch. Some Ring models
            # expose the same posture only as a camera attribute.
            motion_enabled = boolean_state(motion_state)
            if motion_enabled is None:
                motion_enabled = boolean_attribute(
                    camera_state,
                    "motion_detection",
                )

            # Some Ring models expose motion posture inconsistently through
            # Home Assistant. For a known motion-capable camera, allow a
            # configuration fallback so the dashboard does not incorrectly
            # report Unknown or exclude it from the KPI denominator.
            if motion_enabled is None and definition.get("motion_default_enabled") is not None:
                motion_enabled = bool(definition["motion_default_enabled"])

            issues: list[str] = []

            if not available:
                health, label = "critical", "Offline"
                issues.append("Camera unavailable")
            elif battery is not None and battery < CONFIG["ring_critical_battery_percent"]:
                health, label = "critical", "Critical"
                issues.append(f"Battery critical ({battery}%)")
            elif (battery is not None and battery < CONFIG["ring_low_battery_percent"]) or motion_enabled is False:
                health, label = "warning", "Attention"
                if battery is not None and battery < CONFIG["ring_low_battery_percent"]:
                    issues.append(f"Battery low ({battery}%)")
                if motion_enabled is False:
                    issues.append("Motion detection disabled")
            else:
                health, label = "healthy", "Online"

            camera = {
                "id": definition["id"],
                "name": definition["name"],
                "available": available,
                "camera_state": None if not camera_state else camera_state.get("state"),
                "health": health,
                "health_label": label,
                "battery_percent": battery,
                "motion_enabled": motion_enabled,
                "last_activity": activity_raw,
                "last_activity_epoch": activity_epoch,
                "activity_category": activity_attrs.get("category"),
                "activity_answered": activity_attrs.get("answered"),
                "light_state": None if not light_state else light_state.get("state"),
                "siren_state": None if not siren_state else siren_state.get("state"),
                "has_light": bool(definition.get("light_entity")),
                "has_siren": bool(definition.get("siren_entity")),
                "issues": issues,
            }
            cameras.append(camera)
        except Exception as exc:
            errors.append(f"{definition['name']}: {exc}")
            cameras.append({
                "id": definition["id"], "name": definition["name"], "available": False,
                "health": "unknown", "health_label": "Unknown", "battery_percent": None,
                "motion_enabled": None, "last_activity": None, "last_activity_epoch": None,
                "light_state": None, "siren_state": None,
                "has_light": bool(definition.get("light_entity")),
                "has_siren": bool(definition.get("siren_entity")),
                "issues": [str(exc)],
            })

    integration_available = bool(cameras) and not (errors and all(c.get("health") == "unknown" for c in cameras))
    if log_changes:
        apply_transitions(_major_security_transitions(cameras, integration_available))

    total = len(cameras)
    latest_camera = max(
        (camera for camera in cameras if camera.get("last_activity_epoch")),
        key=lambda camera: camera.get("last_activity_epoch") or 0,
        default=None,
    )

    latest_category = None if not latest_camera else latest_camera.get("activity_category")
    if latest_category == "ding":
        latest_event_label = f"{latest_camera['name']} doorbell"
    elif latest_category == "on_demand":
        latest_event_label = f"{latest_camera['name']} live view"
    else:
        latest_event_label = None if not latest_camera else f"{latest_camera['name']} motion"

    summary = {
        "total": total,
        "online": sum(c["available"] for c in cameras),
        "healthy": sum(c["health"] == "healthy" for c in cameras),
        "attention": sum(c["health"] == "warning" for c in cameras),
        "critical": sum(c["health"] == "critical" for c in cameras),
        "unknown": sum(c["health"] == "unknown" for c in cameras),
        "motion_enabled": sum(c.get("motion_enabled") is True for c in cameras),
        "motion_capable": sum(c.get("motion_enabled") is not None for c in cameras),
        "alerts": sum(bool(c.get("issues")) for c in cameras),
        "last_event_epoch": None if not latest_camera else latest_camera.get("last_activity_epoch"),
        "last_event_camera": None if not latest_camera else latest_camera.get("name"),
        "last_event_category": latest_category,
        "last_event_label": latest_event_label,
    }
    overall = "critical" if summary["critical"] else "warning" if summary["attention"] or summary["unknown"] else "healthy"
    return {
        "available": not errors,
        "configured_count": len(CONFIG["ring_cameras"]),
        "overall": overall,
        "summary": summary,
        "cameras": cameras,
        "errors": errors,
        "updated_at": int(time.time()),
    }
