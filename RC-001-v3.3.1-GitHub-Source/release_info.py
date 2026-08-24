from __future__ import annotations

import json
import os
import platform
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
VERSION_FILE = PROJECT_ROOT / "VERSION.json"
MANIFEST_FILE = PROJECT_ROOT / "MANIFEST.json"
BUILD_INFO_FILE = PROJECT_ROOT / "BUILD_INFO.json"
_PROCESS_STARTED_AT = time.time()

_DEFAULT_VERSION: dict[str, Any] = {
    "product": "RC-001",
    "display_name": "Home Operations Center",
    "version": "unknown",
    "version_short": "unknown",
    "build": "unknown",
    "release_type": "development",
    "release_type_label": "Development",
    "codename": "Unknown",
    "database_schema": 0,
    "compatible_from": "unknown",
}


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if isinstance(value, dict):
            return value
    except (OSError, json.JSONDecodeError):
        pass
    return dict(default)


def _read_os_release() -> str:
    path = Path("/etc/os-release")
    try:
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            values[key] = raw_value.strip().strip('"')
        return values.get("PRETTY_NAME") or values.get("NAME") or platform.platform()
    except OSError:
        return platform.platform()


def _read_device_model() -> str:
    candidates = (
        Path("/proc/device-tree/model"),
        Path("/sys/firmware/devicetree/base/model"),
    )
    for path in candidates:
        try:
            model = path.read_text(encoding="utf-8", errors="ignore").replace("\x00", "").strip()
            if model:
                return model
        except OSError:
            continue
    return platform.machine() or "Unknown hardware"


def get_release_metadata() -> dict[str, Any]:
    version = _read_json(VERSION_FILE, _DEFAULT_VERSION)
    manifest = _read_json(MANIFEST_FILE, {})
    build_info = _read_json(BUILD_INFO_FILE, {})
    return {
        **_DEFAULT_VERSION,
        **version,
        "manifest_version": manifest.get("manifest_version"),
        "built_at": build_info.get("built_at"),
        "revision": build_info.get("revision", "local"),
    }


def get_build_information() -> dict[str, Any]:
    metadata = get_release_metadata()
    uptime_seconds = max(0, int(time.time() - _PROCESS_STARTED_AT))
    return {
        **metadata,
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "operating_system": _read_os_release(),
        "hardware": _read_device_model(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "process_id": os.getpid(),
        "application_uptime_seconds": uptime_seconds,
    }
