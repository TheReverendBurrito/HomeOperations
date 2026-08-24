from __future__ import annotations

import re
import subprocess
import threading
import time
from typing import Any

from config import CONFIG
import runtime_state

HC_IN_BASE = "1.3.6.1.2.1.31.1.1.1.6"
HC_OUT_BASE = "1.3.6.1.2.1.31.1.1.1.10"


def _parse_counter(line: str) -> int:
    matches = re.findall(r"-?\d+", line)
    if not matches:
        raise ValueError(f"Unable to parse SNMP counter: {line!r}")
    return int(matches[-1])


def _read_counters() -> dict[str, dict[str, int]]:
    wan_indexes = CONFIG["snmp_wan_ifindexes"]
    oids: list[str] = []
    order: list[tuple[str, str]] = []

    for wan_id, ifindex in wan_indexes.items():
        oids.append(f"{HC_IN_BASE}.{ifindex}")
        order.append((str(wan_id), "in_octets"))
        oids.append(f"{HC_OUT_BASE}.{ifindex}")
        order.append((str(wan_id), "out_octets"))

    command = [
        CONFIG["snmpget_path"],
        "-v2c",
        "-c",
        CONFIG["snmp_community"],
        "-t",
        str(CONFIG["snmp_timeout_seconds"]),
        "-r",
        str(CONFIG["snmp_retries"]),
        "-Oqv",
        f"{CONFIG['snmp_host']}:{CONFIG['snmp_port']}",
        *oids,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=max(5, CONFIG["snmp_timeout_seconds"] + 3),
        check=False,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(message or f"snmpget exited with code {result.returncode}")

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) != len(order):
        raise RuntimeError(
            f"Expected {len(order)} SNMP counters but received {len(lines)}"
        )

    counters: dict[str, dict[str, int]] = {}
    for (wan_id, field), line in zip(order, lines):
        counters.setdefault(wan_id, {})[field] = _parse_counter(line)

    return counters


def _calculate_rates(
    previous: dict[str, dict[str, int]],
    current: dict[str, dict[str, int]],
    elapsed: float,
) -> dict[str, dict[str, Any]]:
    rates: dict[str, dict[str, Any]] = {}
    total_mbps = 0.0

    for wan_id, counters in current.items():
        prior = previous.get(wan_id)
        download_mbps = 0.0
        upload_mbps = 0.0

        if prior and elapsed > 0:
            in_delta = counters["in_octets"] - prior["in_octets"]
            out_delta = counters["out_octets"] - prior["out_octets"]

            if in_delta >= 0:
                download_mbps = in_delta * 8 / elapsed / 1_000_000
            if out_delta >= 0:
                upload_mbps = out_delta * 8 / elapsed / 1_000_000

        download_mbps = round(download_mbps, 2)
        upload_mbps = round(upload_mbps, 2)
        activity_mbps = download_mbps + upload_mbps
        total_mbps += activity_mbps

        rates[wan_id] = {
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "activity_mbps": round(activity_mbps, 2),
            "in_octets": counters["in_octets"],
            "out_octets": counters["out_octets"],
            "traffic_share_percent": 0.0,
        }

    if total_mbps > 0.01:
        for values in rates.values():
            values["traffic_share_percent"] = round(
                values["activity_mbps"] / total_mbps * 100,
                1,
            )

    return rates


def _worker() -> None:
    previous: dict[str, dict[str, int]] = {}
    previous_time: float | None = None

    while True:
        started = time.time()
        try:
            current = _read_counters()
            now = time.time()
            elapsed = now - previous_time if previous_time is not None else 0.0
            rates = _calculate_rates(previous, current, elapsed)

            runtime_state.set_snmp_status(
                {
                    "available": True,
                    "last_success": int(now),
                    "error": None,
                    "wans": rates,
                }
            )
            previous = current
            previous_time = now
        except Exception as exc:
            existing = runtime_state.get_snmp_status()
            existing["available"] = False
            existing["error"] = str(exc)
            runtime_state.set_snmp_status(existing)
            print(f"SNMP monitor failed: {exc}")

        delay = max(0.25, CONFIG["snmp_poll_seconds"] - (time.time() - started))
        time.sleep(delay)


def start_snmp_worker() -> threading.Thread | None:
    if not CONFIG["snmp_enabled"]:
        return None

    thread = threading.Thread(
        target=_worker,
        daemon=True,
        name="snmp-monitor",
    )
    thread.start()
    return thread
