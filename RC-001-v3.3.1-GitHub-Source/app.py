from __future__ import annotations

import time
from urllib.parse import urlencode

from flask import Flask, jsonify, render_template, request

from config import CONFIG
from database import get_recent_logs, init_db, log_event
from peplink import login as peplink_login
import runtime_state
from speedtest_service import start_worker
from snmp_monitor import start_snmp_worker
from status_service import collect_status
from wled import PRESETS, set_status
from ring_service import collect_ring_status
from networking_service import collect_networking_status
from networking_registry_api import RegistryValidationError, delete_registry_device, get_registry_payload, update_registry_device
from release_info import get_build_information, get_release_metadata
from startup_validation import run_startup_validation, validate_or_raise
from alert_monitor import get_alert_snapshot, start_alert_worker

app = Flask(__name__)
STARTUP_VALIDATION_REPORT = None


@app.context_processor
def inject_release_metadata():
    return {"release_info": get_release_metadata()}


def render_console_page(
    template_name: str,
    active_page: str,
    **context: object,
):
    return render_template(
        template_name,
        poll_seconds=CONFIG["poll_seconds"],
        active_page=active_page,
        configured_camera_count=len(CONFIG["ring_cameras"]),
        **context,
    )


@app.get("/")
def home():
    return render_console_page("home.html", "home")


@app.get("/environment")
def environment_page():
    latitude = CONFIG["weather_radar_latitude"]
    longitude = CONFIG["weather_radar_longitude"]
    zoom = CONFIG["weather_radar_zoom"]
    radar_parameters = {
        "lat": latitude,
        "lon": longitude,
        "detailLat": latitude,
        "detailLon": longitude,
        "width": 1200,
        "height": 675,
        "zoom": zoom,
        "level": "surface",
        "overlay": "radar",
        "product": "radar",
        "menu": "",
        "message": "true",
        "marker": "true",
        "calendar": "now",
        "pressure": "",
        "type": "map",
        "location": "coordinates",
        "detail": "",
        "metricWind": "mph",
        "metricTemp": "°F",
        "radarRange": "-1",
    }
    radar_url = f"https://embed.windy.com/embed2.html?{urlencode(radar_parameters)}"
    full_radar_url = (
        "https://www.windy.com/?radar,"
        f"{latitude:.4f},{longitude:.4f},{zoom}"
    )
    return render_console_page(
        "environment.html",
        "environment",
        weather_radar_enabled=CONFIG["weather_radar_enabled"],
        weather_radar_url=radar_url,
        weather_radar_full_url=full_radar_url,
    )


@app.get("/security")
def security_page():
    return render_console_page("security.html", "security")


@app.get("/lighting")
def lighting_page():
    return render_console_page("lighting.html", "lighting")


@app.get("/operations")
def operations_page():
    return render_console_page("operations.html", "operations")


@app.get("/networking")
def networking_page():
    return render_console_page("networking.html", "networking")


@app.get("/api/build")
def api_build():
    return jsonify(get_build_information())


@app.get("/api/startup-validation")
def api_startup_validation():
    report = run_startup_validation(include_connectivity=True)
    return jsonify(report.to_dict()), 200 if report.ok else 503


@app.get("/api/status")
def api_status():
    try:
        return jsonify(collect_status(update_lights=True))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/api/security/cameras")
def api_security_cameras():
    try:
        return jsonify(collect_ring_status(log_changes=True))
    except Exception as exc:
        return jsonify({
            "available": False,
            "configured_count": len(CONFIG["ring_cameras"]),
            "error": str(exc),
            "cameras": [],
        }), 503


@app.get("/api/logs")
def api_logs():
    return jsonify(get_recent_logs())


@app.get("/api/alerts")
def api_alerts():
    return jsonify(get_alert_snapshot())


@app.get("/api/networking")
def api_networking():
    try:
        return jsonify(collect_networking_status())
    except Exception as exc:
        return jsonify({"available": False, "error": str(exc), "summary": {}, "topology": {}}), 503


@app.get("/api/lights/auto")
def clear_manual_light():
    runtime_state.MANUAL_OVERRIDE_STATUS = None
    runtime_state.MANUAL_OVERRIDE_UNTIL = 0
    log_event("automation", "⚙ Automatic cabinet lighting restored")
    status = collect_status(update_lights=True)
    return jsonify(
        {
            "ok": True,
            "status": status["lighting_status"],
            "label": status["lighting_label"],
        }
    )


@app.get("/api/lights/<status>")
def manual_light(status: str):
    if status not in PRESETS:
        return jsonify({"error": "invalid status"}), 400

    runtime_state.MANUAL_OVERRIDE_STATUS = status
    runtime_state.MANUAL_OVERRIDE_UNTIL = (
        time.time() + CONFIG["manual_override_seconds"]
    )
    set_status(status, force=True)
    runtime_state.WLED_AVAILABLE = True
    log_event(
        "lighting",
        f"💡 Manual cabinet mode enabled: {PRESETS[status]['label']}",
    )

    return jsonify(
        {
            "ok": True,
            "status": status,
            "label": PRESETS[status]["label"],
            "override_seconds": CONFIG["manual_override_seconds"],
        }
    )


@app.get("/api/networking/registry")
def api_networking_registry():
    return jsonify(get_registry_payload())

@app.put("/api/networking/registry/<path:mac>")
def api_networking_registry_update(mac):
    try:
        return jsonify(update_registry_device(mac, request.get_json(silent=True) or {}))
    except RegistryValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500

@app.delete("/api/networking/registry/<path:mac>")
def api_networking_registry_delete(mac):
    try:
        return jsonify(delete_registry_device(mac))
    except RegistryValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500

def main() -> None:
    global STARTUP_VALIDATION_REPORT
    STARTUP_VALIDATION_REPORT = validate_or_raise(include_connectivity=True)
    init_db()
    peplink_login()
    start_worker()
    start_snmp_worker()
    start_alert_worker()
    app.run(host="0.0.0.0", port=5050)


if __name__ == "__main__":
    main()
