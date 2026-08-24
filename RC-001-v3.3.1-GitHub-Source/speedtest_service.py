from __future__ import annotations

import json
import math
import subprocess
import threading
import time
from typing import Any

from config import CONFIG
from database import log_event
import runtime_state


MAX_REASONABLE_PING_MS = 5000.0


def _to_float(value: Any) -> float | None:
    """
    Convert a value to a finite float.

    Returns None for missing, invalid, NaN, or infinite values.
    """
    try:
        number = float(value)

        if not math.isfinite(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


def _nested_value(
    data: dict[str, Any],
    *keys: str,
) -> Any:
    """
    Safely retrieve a value from nested dictionaries.
    """
    current: Any = data

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def _format_value(value: float | None) -> str:
    """
    Format an optional numeric value for console and event output.
    """
    return "--" if value is None else str(value)


def _parse_ookla_result(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Parse JSON from the official Ookla Speedtest CLI.

    Ookla reports bandwidth in bytes per second.
    RC001 converts those values to megabits per second.
    """

    download_bandwidth = _to_float(
        _nested_value(data, "download", "bandwidth")
    )

    upload_bandwidth = _to_float(
        _nested_value(data, "upload", "bandwidth")
    )

    raw_ping = _to_float(
        _nested_value(data, "ping", "latency")
    )

    raw_jitter = _to_float(
        _nested_value(data, "ping", "jitter")
    )

    download = (
        round(download_bandwidth * 8 / 1_000_000, 1)
        if download_bandwidth is not None
        and download_bandwidth >= 0
        else None
    )

    upload = (
        round(upload_bandwidth * 8 / 1_000_000, 1)
        if upload_bandwidth is not None
        and upload_bandwidth >= 0
        else None
    )

    ping = (
        round(raw_ping, 1)
        if raw_ping is not None
        and 0 < raw_ping <= MAX_REASONABLE_PING_MS
        else None
    )

    jitter = (
        round(raw_jitter, 1)
        if raw_jitter is not None
        and raw_jitter >= 0
        else None
    )

    server_name = _nested_value(
        data,
        "server",
        "name",
    )

    server_location = _nested_value(
        data,
        "server",
        "location",
    )

    result_url = _nested_value(
        data,
        "result",
        "url",
    )

    return {
        "download": download,
        "upload": upload,
        "ping": ping,
        "jitter": jitter,
        "server": (
            str(server_name)
            if server_name
            else None
        ),
        "server_location": (
            str(server_location)
            if server_location
            else None
        ),
        "result_url": (
            str(result_url)
            if result_url
            else None
        ),
        "timestamp": int(time.time()),
    }


def _empty_speedtest() -> dict[str, Any]:
    """
    Return the default empty speed-test structure.
    """
    return {
        "download": None,
        "upload": None,
        "ping": None,
        "jitter": None,
        "server": None,
        "server_location": None,
        "result_url": None,
        "timestamp": 0,
    }


def run_speedtest() -> None:
    """
    Run the official Ookla Speedtest CLI and store the latest result.
    """

    try:
        result = subprocess.run(
            [
                CONFIG["speedtest_path"],
                "--accept-license",
                "--accept-gdpr",
                "--format=json",
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

        if result.returncode != 0:
            error_message = (
                result.stderr.strip()
                or result.stdout.strip()
                or f"Speedtest exited with code {result.returncode}"
            )

            raise RuntimeError(error_message)

        raw_output = result.stdout.strip()

        if not raw_output:
            raise RuntimeError(
                "Speedtest returned no output."
            )

        data = json.loads(raw_output)
        current = _parse_ookla_result(data)

        if (
            current["download"] is None
            and current["upload"] is None
            and current["ping"] is None
        ):
            raise RuntimeError(
                "Speedtest returned no usable measurements."
            )

        runtime_state.set_speedtest(current)

        download_text = _format_value(
            current["download"]
        )

        upload_text = _format_value(
            current["upload"]
        )

        ping_text = _format_value(
            current["ping"]
        )

        jitter_text = _format_value(
            current["jitter"]
        )

        server_text = (
            current["server"]
            or "Unknown server"
        )

        if current["server_location"]:
            server_text = (
                f"{server_text}, "
                f"{current['server_location']}"
            )

        log_event(
            "speedtest",
            (
                "📊 Internet test completed — "
                f"↓ {download_text} Mbps · "
                f"↑ {upload_text} Mbps · "
                f"Latency {ping_text} ms · "
                f"Jitter {jitter_text} ms"
            ),
        )

        print(
            "Speed test completed:"
            f"\n  Download: {download_text} Mbps"
            f"\n  Upload:   {upload_text} Mbps"
            f"\n  Latency:  {ping_text} ms"
            f"\n  Jitter:   {jitter_text} ms"
            f"\n  Server:   {server_text}"
        )

    except subprocess.TimeoutExpired:
        print(
            "Speed test failed: "
            "command timed out after 180 seconds."
        )

    except json.JSONDecodeError as exc:
        print(
            "Speed test failed: "
            f"invalid JSON response: {exc}"
        )

    except Exception as exc:
        print(f"Speed test failed: {exc}")

        previous = runtime_state.get_speedtest()

        if not previous:
            runtime_state.set_speedtest(
                _empty_speedtest()
            )


def _worker() -> None:
    """
    Run speed tests continuously at the configured interval.
    """
    while True:
        run_speedtest()

        time.sleep(
            CONFIG["speedtest_interval_seconds"]
        )


def start_worker() -> threading.Thread:
    """
    Start the background Ookla Speedtest worker.
    """
    thread = threading.Thread(
        target=_worker,
        daemon=True,
        name="speedtest-worker",
    )

    thread.start()

    return thread