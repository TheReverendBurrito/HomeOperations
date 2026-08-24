from __future__ import annotations

import os
import socket
import time
from typing import Any
from urllib.parse import urlparse

from config import CONFIG
from device_classifier import CATEGORY_LABELS, classify_device
from device_registry import load_registry, normalize_mac
from peplink_clients import PeplinkClientDiscoveryError, discover_peplink_clients
from ring_service import collect_ring_status
from topology_builder import build_topology


INFRASTRUCTURE_IPS = {}


def _host_from_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"http://{value}")
    return parsed.hostname


def _tcp_reachable(host: str | None, port: int, timeout: float = 0.75) -> bool | None:
    if not host:
        return None
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _service_status(
    *,
    name: str,
    device_id: str,
    address: str | None,
    port: int | None,
    connection: str,
    notes: str,
) -> dict[str, Any]:
    reachable = _tcp_reachable(address, port) if port else None
    status = "online" if reachable is True else "offline" if reachable is False else "configured"
    return {
        "id": device_id,
        "name": name,
        "category": "infrastructure",
        "category_label": "Infrastructure",
        "status": status,
        "status_label": status.title(),
        "address": address,
        "ip": address,
        "connection": connection,
        "notes": notes,
        "registered": True,
        "is_new": False,
    }


def _infrastructure_devices(
    *,
    total_clients: int,
    active_clients: int,
    wireless_clients: int,
) -> list[dict[str, Any]]:
    ha_url = os.getenv("HOME_ASSISTANT_URL") or os.getenv("HA_URL")
    wled_url = os.getenv("WLED_BASE_URL") or os.getenv("WLED_URL")
    peplink_url = os.getenv("PEPLINK_URL") or os.getenv("PEPLINK_BASE_URL")
    controller_address = os.getenv("RC001_CONTROLLER_ADDRESS") or None

    return [
        {
            "id": "rc001",
            "name": "RC-001 Controller",
            "category": "infrastructure",
            "category_label": "Infrastructure",
            "status": "online",
            "status_label": "Online",
            "address": controller_address,
            "ip": controller_address,
            "connection": "Wired",
            "notes": "Raspberry Pi 5 application host",
            "metrics": {
                "platform": "Raspberry Pi 5",
                "service": "RC-001",
            },
            "registered": True,
            "is_new": False,
        },
        {
            **_service_status(
                name="Peplink B One",
                device_id="peplink",
                address=_host_from_url(peplink_url),
                port=443,
                connection="Wired",
                notes="Routing core and WAN aggregation",
            ),
            "metrics": {
                "wan_count": 3,
                "client_count": total_clients,
                "active_clients": active_clients,
            },
        },
        {
            "id": "deco_mesh",
            "name": "TP-Link Deco Mesh",
            "category": "infrastructure",
            "category_label": "Infrastructure",
            "status": "configured",
            "status_label": "Configured",
            "address": None,
            "ip": None,
            "connection": "Access Point",
            "notes": "Wireless distribution layer",
            "metrics": {
                "ap_count": 3,
                "wireless_clients": wireless_clients,
            },
            "registered": True,
            "is_new": False,
        },
        {
            **_service_status(
                name="Home Assistant",
                device_id="home_assistant",
                address=_host_from_url(ha_url),
                port=8123,
                connection="Wired",
                notes="Automation and Ring integration platform",
            ),
            "metrics": {
                "integration": "Connected",
                "camera_count": len(CONFIG["ring_cameras"]),
            },
        },
        {
            **_service_status(
                name="Cabinet WLED",
                device_id="wled",
                address=_host_from_url(wled_url),
                port=80,
                connection="Wireless",
                notes="Cabinet status-light controller",
            ),
            "metrics": {
                "role": "Status lighting",
            },
        },
        {
            "id": "ac_infinity",
            "name": "AC Infinity Controller",
            "category": "infrastructure",
            "category_label": "Infrastructure",
            "status": "configured",
            "status_label": "Configured",
            "address": None,
            "ip": None,
            "connection": "Wireless",
            "notes": "Environmental telemetry through Home Assistant",
            "metrics": {
                "role": "Environmental telemetry",
            },
            "registered": True,
            "is_new": False,
        },
    ]


def _security_devices() -> tuple[list[dict[str, Any]], list[str]]:
    try:
        ring = collect_ring_status()
    except Exception as exc:
        return [], [f"Ring telemetry failed: {type(exc).__name__}: {exc}"]

    cameras = []
    for camera in ring.get("cameras", []):
        cameras.append(
            {
                "id": camera.get("id"),
                "name": camera.get("name", "Camera"),
                "category": "security",
                "category_label": "Security",
                "status": "online" if camera.get("available") else "offline",
                "status_label": "Online" if camera.get("available") else "Offline",
                "address": None,
                "ip": None,
                "connection": "Wireless",
                "battery_percent": camera.get("battery_percent"),
                "motion_enabled": camera.get("motion_enabled"),
                "health": camera.get("health", "unknown"),
                "health_label": camera.get("health_label", "Unknown"),
                "last_activity_epoch": camera.get("last_activity_epoch"),
                "issues": camera.get("issues", []),
                "registered": True,
                "is_new": False,
            }
        )
    return cameras, list(ring.get("errors", []))


def _discovered_clients() -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    try:
        raw_clients, metadata = discover_peplink_clients(include_inactive=True)
    except PeplinkClientDiscoveryError as exc:
        return [], {"source": "Peplink Router API", "available": False}, [str(exc)]

    registry = load_registry()["devices"]
    classified: list[dict[str, Any]] = []

    for client in raw_clients:
        mac = normalize_mac(client.get("mac"))
        entry = registry.get(mac, {}) if mac else {}

        if client.get("ip") in INFRASTRUCTURE_IPS and not entry:
            entry = {
                "name": INFRASTRUCTURE_IPS[client["ip"]],
                "category": "infrastructure",
                "icon": "server",
            }

        classified.append(classify_device(client, entry))

    metadata["available"] = True
    metadata["registered_count"] = sum(item["registered"] for item in classified)
    metadata["new_count"] = sum(item["is_new"] for item in classified)
    return classified, metadata, []


def collect_networking_status() -> dict[str, Any]:
    discovered, discovery, discovery_errors = _discovered_clients()

    clients = [
        item for item in discovered
        if item["category"] not in {"infrastructure", "security"}
    ]
    wireless_clients = [
        item
        for item in clients
        if str(item.get("connection_type") or item.get("connection") or "").lower()
        in {"wifi", "wireless", "wi-fi"}
    ]

    infrastructure = _infrastructure_devices(
        total_clients=len(clients),
        active_clients=sum(bool(item.get("active")) for item in clients),
        wireless_clients=len(wireless_clients),
    )
    security, security_errors = _security_devices()
    unknown = [item for item in clients if item["category"] == "unknown"]

    category_counts = {
        category: sum(item["category"] == category for item in clients)
        for category in ("iot", "computers", "entertainment", "mobile", "unknown")
    }

    offline = (
        sum(item.get("status") == "offline" for item in infrastructure)
        + sum(item.get("status") == "offline" for item in security)
        + sum(item.get("status") == "offline" for item in clients)
    )

    summary = {
        "total": len(infrastructure) + len(security) + len(clients),
        "infrastructure": len(infrastructure),
        "security": len(security),
        "clients": len(clients),
        "active_clients": sum(bool(item.get("active")) for item in clients),
        "unknown": len(unknown),
        "offline": offline,
        "new": sum(item.get("is_new") for item in clients),
        "categories": category_counts,
        "data_mode": "live-discovery",
    }

    topology = build_topology(
        infrastructure=infrastructure,
        security=security,
        clients=clients,
        wan_names=["Work DSL", "Home DSL", "T-Mobile"],
    )

    return {
        "available": not discovery_errors,
        "logical_topology": True,
        "summary": summary,
        "topology": topology,
        "infrastructure": infrastructure,
        "security": security,
        "clients": clients,
        "unknown": unknown,
        "inventory": clients,
        "category_labels": CATEGORY_LABELS,
        "discovery": discovery,
        "errors": [*security_errors, *discovery_errors],
        "updated_at": int(time.time()),
        "notice": "Live topology and infrastructure intelligence are derived from trusted RC-001 data sources.",
    }
