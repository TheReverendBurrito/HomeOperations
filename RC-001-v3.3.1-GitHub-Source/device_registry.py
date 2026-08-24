from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from config import BASE_DIR


REGISTRY_PATH = BASE_DIR / "data" / "device_registry.json"
MAC_PATTERN = re.compile(r"^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$")


def normalize_mac(value: str | None) -> str | None:
    if not value:
        return None
    compact = re.sub(r"[^0-9A-Fa-f]", "", value)
    if len(compact) != 12:
        return None
    normalized = ":".join(compact[index:index + 2] for index in range(0, 12, 2)).upper()
    return normalized if MAC_PATTERN.match(normalized) else None


def _default_registry() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "devices": {},
    }


def ensure_registry() -> Path:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        save_registry(_default_registry())
    return REGISTRY_PATH


def load_registry() -> dict[str, Any]:
    ensure_registry()
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = _default_registry()

    if not isinstance(payload, dict):
        payload = _default_registry()
    payload.setdefault("schema_version", 1)
    payload.setdefault("devices", {})
    if not isinstance(payload["devices"], dict):
        payload["devices"] = {}
    return payload


def save_registry(payload: dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=REGISTRY_PATH.parent,
        prefix=".device_registry.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)

    os.chmod(temporary, 0o600)
    os.replace(temporary, REGISTRY_PATH)


def registry_entry(mac: str | None) -> dict[str, Any] | None:
    normalized = normalize_mac(mac)
    if not normalized:
        return None
    value = load_registry()["devices"].get(normalized)
    return value if isinstance(value, dict) else None


def registered_macs() -> set[str]:
    return set(load_registry()["devices"].keys())
