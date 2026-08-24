from __future__ import annotations

import re
from typing import Any


CATEGORY_LABELS = {
    "infrastructure": "Infrastructure",
    "security": "Security",
    "iot": "IoT",
    "computers": "Computers",
    "entertainment": "Entertainment",
    "mobile": "Mobile",
    "unknown": "Unknown",
}

RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "infrastructure",
        (
            "raspberrypi", "rc-001", "rc001", "homeassistant", "home-assistant",
            "wled", "peplink", "pepwave", "deco", "ac infinity", "controller 69",
        ),
    ),
    (
        "security",
        (
            "ring", "doorbell", "stick up cam", "spotlight cam", "floodlight cam",
            "front door", "deck garage", "side deck",
        ),
    ),
    (
        "entertainment",
        (
            "samsung tv", "smart-tv", "smarttv", "roku", "appletv", "apple tv",
            "chromecast", "firetv", "fire tv", "xbox", "playstation", "ps5",
            "nintendo", "peacock",
        ),
    ),
    (
        "computers",
        (
            "macbook", "imac", "mac mini", "windows", "desktop", "laptop",
            "workstation", "thinkpad", "surface", "chromebook",
        ),
    ),
    (
        "mobile",
        (
            "iphone", "ipad", "android", "pixel", "galaxy", "phone", "tablet",
        ),
    ),
    (
        "iot",
        (
            "echo", "alexa", "amazon", "google home", "nest", "printer", "canon",
            "brother", "epson", "hp printer", "thermostat", "sensor", "switch",
            "plug", "bulb", "vacuum", "roomba", "camera", "esp", "tuya",
        ),
    ),
]

ICON_BY_CATEGORY = {
    "infrastructure": "server",
    "security": "shield",
    "iot": "cpu",
    "computers": "monitor",
    "entertainment": "tv",
    "mobile": "smartphone",
    "unknown": "help-circle",
}


def _search_text(device: dict[str, Any]) -> str:
    values = [
        device.get("name"),
        device.get("hostname"),
        device.get("vendor"),
        device.get("client_type"),
        device.get("essid"),
    ]
    return " ".join(str(value) for value in values if value).lower()


def classify_device(
    device: dict[str, Any],
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry or {}
    text = _search_text(device)

    registry_category = str(registry.get("category") or "").strip().lower()
    if registry_category in CATEGORY_LABELS:
        category = registry_category
        source = "registry"
    else:
        category = "unknown"
        source = "unclassified"
        for candidate, keywords in RULES:
            if any(keyword in text for keyword in keywords):
                category = candidate
                source = "automatic"
                break

    registry_name = str(registry.get("name") or "").strip()
    discovered_name = str(
        device.get("name")
        or device.get("hostname")
        or device.get("vendor")
        or ""
    ).strip()

    if registry_name:
        display_name = registry_name
        name_source = "registry"
    elif discovered_name:
        display_name = discovered_name
        name_source = "discovered"
    else:
        ip = device.get("ip") or device.get("address") or "unidentified"
        display_name = f"Unknown Device ({ip})"
        name_source = "generated"

    icon = str(registry.get("icon") or ICON_BY_CATEGORY[category])
    notes = str(registry.get("notes") or "").strip()

    return {
        **device,
        "name": display_name,
        "name_source": name_source,
        "category": category,
        "category_label": CATEGORY_LABELS[category],
        "classification_source": source,
        "icon": icon,
        "notes": notes,
        "registered": bool(registry),
        "is_new": not bool(registry) and category == "unknown",
    }
