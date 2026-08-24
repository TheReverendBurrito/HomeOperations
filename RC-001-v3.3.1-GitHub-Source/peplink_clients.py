from __future__ import annotations

import time
from typing import Any

from device_registry import normalize_mac
from peplink import get as peplink_get


class PeplinkClientDiscoveryError(RuntimeError):
    pass


def discover_peplink_clients(
    *,
    include_inactive: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()

    try:
        response = peplink_get(
            "/api/status.client",
            params={
                "activeOnly": "no" if include_inactive else "yes",
                "outputWeight": "full",
                "size": 1000,
            },
        )
    except Exception as exc:
        raise PeplinkClientDiscoveryError(
            f"Peplink client discovery failed: {type(exc).__name__}: {exc}"
        ) from exc

    raw_clients = response.get("list") if isinstance(response, dict) else []
    if not isinstance(raw_clients, list):
        raw_clients = []

    now = int(time.time())
    clients: list[dict[str, Any]] = []

    for raw in raw_clients:
        if not isinstance(raw, dict):
            continue

        mac = normalize_mac(raw.get("mac"))
        ip = raw.get("ip")
        active = bool(raw.get("active"))
        connection_type = str(raw.get("connectionType") or "other").lower()
        signal = raw.get("signal") or raw.get("signalStrength") or {}
        speed = raw.get("speed") or {}
        lease = raw.get("lease") or {}

        clients.append(
            {
                "id": mac or str(ip or raw.get("name") or len(clients)),
                "mac": mac,
                "ip": ip,
                "address": ip,
                "hostname": raw.get("name"),
                "name": raw.get("name"),
                "vendor": raw.get("vendor"),
                "client_type": raw.get("clientType"),
                "connection_type": connection_type,
                "connection": connection_type.title(),
                "active": active,
                "status": "online" if active else "offline",
                "status_label": "Online" if active else "Offline",
                "bssid": raw.get("bssid"),
                "essid": raw.get("essid"),
                "vlan_id": raw.get("vlanId"),
                "port": raw.get("port"),
                "signal_dbm": signal.get("strength", signal.get("value"))
                if isinstance(signal, dict)
                else None,
                "signal_level": signal.get("level")
                if isinstance(signal, dict)
                else None,
                "download_kbps": speed.get("download")
                if isinstance(speed, dict)
                else None,
                "upload_kbps": speed.get("upload")
                if isinstance(speed, dict)
                else None,
                "lease_type": lease.get("type")
                if isinstance(lease, dict)
                else None,
                "lease_expires_seconds": lease.get("expiresIn")
                if isinstance(lease, dict)
                else None,
                "last_seen_epoch": now if active else None,
                "source": "peplink-status-client",
            }
        )

    clients.sort(
        key=lambda item: (
            not item["active"],
            str(item.get("name") or "").lower(),
            str(item.get("ip") or ""),
        )
    )

    metadata = {
        "source": "Peplink Router API status.client",
        "client_count": len(clients),
        "active_count": sum(item["active"] for item in clients),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "collected_at": now,
    }
    return clients, metadata
