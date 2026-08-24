from __future__ import annotations

from typing import Any

from device_classifier import CATEGORY_LABELS
from device_registry import load_registry, normalize_mac, save_registry


ALLOWED_CATEGORIES = set(CATEGORY_LABELS)


class RegistryValidationError(ValueError):
    pass


def _clean(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        raise RegistryValidationError(f"Value exceeds {limit} characters")
    return text


def get_registry_payload() -> dict[str, Any]:
    registry = load_registry()
    devices = registry.get("devices", {})
    return {
        "schema_version": registry.get("schema_version", 1),
        "devices": devices,
        "categories": CATEGORY_LABELS,
        "count": len(devices),
    }


def update_registry_device(mac: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_mac(mac)
    if not normalized:
        raise RegistryValidationError("A valid MAC address is required")

    name = _clean(payload.get("name"), 80)
    category = _clean(payload.get("category"), 32).lower()
    notes = _clean(payload.get("notes"), 240)

    if not name:
        raise RegistryValidationError("Friendly name is required")
    if category not in ALLOWED_CATEGORIES:
        raise RegistryValidationError("Invalid category")

    registry = load_registry()
    devices = registry.setdefault("devices", {})
    devices[normalized] = {
        "name": name,
        "category": category,
        "icon": _clean(payload.get("icon"), 40) or "device",
        "notes": notes,
    }
    save_registry(registry)
    return {"mac": normalized, "entry": devices[normalized], "registry_count": len(devices)}


def delete_registry_device(mac: str) -> dict[str, Any]:
    normalized = normalize_mac(mac)
    if not normalized:
        raise RegistryValidationError("A valid MAC address is required")

    registry = load_registry()
    devices = registry.setdefault("devices", {})
    removed = devices.pop(normalized, None)
    save_registry(registry)
    return {"mac": normalized, "removed": removed is not None, "registry_count": len(devices)}
