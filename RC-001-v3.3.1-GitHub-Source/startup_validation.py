from __future__ import annotations

import os
import shutil
import socket
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from config import BASE_DIR, CONFIG


@dataclass(frozen=True)
class ValidationCheck:
    check_id: str
    label: str
    status: str
    message: str
    required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StartupValidationReport:
    ok: bool
    fatal_count: int
    warning_count: int
    checks: tuple[ValidationCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "fatal_count": self.fatal_count,
            "warning_count": self.warning_count,
            "checks": [check.to_dict() for check in self.checks],
        }


class StartupValidationError(RuntimeError):
    def __init__(self, report: StartupValidationReport):
        self.report = report
        fatal_messages = [
            check.message
            for check in report.checks
            if check.status == "fail"
        ]
        super().__init__("; ".join(fatal_messages) or "Startup validation failed")


def _pass(check_id: str, label: str, message: str, *, required: bool) -> ValidationCheck:
    return ValidationCheck(check_id, label, "pass", message, required)


def _warn(check_id: str, label: str, message: str) -> ValidationCheck:
    return ValidationCheck(check_id, label, "warning", message, False)


def _fail(check_id: str, label: str, message: str) -> ValidationCheck:
    return ValidationCheck(check_id, label, "fail", message, True)


def _check_env_file() -> ValidationCheck:
    env_path = BASE_DIR / ".env"
    if env_path.is_file():
        return _pass("env_file", ".env file", f"Found {env_path}", required=True)
    return _fail("env_file", ".env file", f"Required file is missing: {env_path}")


def _check_required_directories() -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    for name in ("templates", "static", "data", "backups"):
        path = BASE_DIR / name
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".rc001-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            checks.append(
                _pass(
                    f"directory_{name}",
                    f"{name} directory",
                    f"Readable and writable: {path}",
                    required=True,
                )
            )
        except OSError as exc:
            checks.append(
                _fail(
                    f"directory_{name}",
                    f"{name} directory",
                    f"Directory is not writable: {path}: {exc}",
                )
            )
    return checks


def _check_database() -> ValidationCheck:
    database_path = Path(CONFIG["database"])
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path, timeout=5) as connection:
            connection.execute("PRAGMA quick_check")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS startup_validation_probe "
                "(id INTEGER PRIMARY KEY, checked_at INTEGER)"
            )
            connection.commit()
        return _pass(
            "database",
            "SQLite database",
            f"Database opened successfully: {database_path}",
            required=True,
        )
    except (OSError, sqlite3.Error) as exc:
        return _fail(
            "database",
            "SQLite database",
            f"Unable to open database {database_path}: {exc}",
        )


def _check_peplink_credentials() -> ValidationCheck:
    missing = []
    if not str(CONFIG.get("peplink_base_url") or "").strip():
        missing.append("PEPLINK_BASE_URL")
    if not str(CONFIG.get("peplink_username") or "").strip():
        missing.append("PEPLINK_USERNAME")
    if not str(CONFIG.get("peplink_password") or "").strip():
        missing.append("PEPLINK_PASSWORD")
    if missing:
        return _fail(
            "peplink_credentials",
            "Peplink credentials",
            "Missing required setting(s): " + ", ".join(missing),
        )
    return _pass(
        "peplink_credentials",
        "Peplink credentials",
        "Peplink URL, username, and password are configured",
        required=True,
    )


def _check_home_assistant_configuration() -> ValidationCheck:
    missing = []
    if not str(CONFIG.get("home_assistant_url") or "").strip():
        missing.append("HOME_ASSISTANT_URL")
    if not str(CONFIG.get("home_assistant_token") or "").strip():
        missing.append("HOME_ASSISTANT_TOKEN")
    if missing:
        return _fail(
            "home_assistant_configuration",
            "Home Assistant configuration",
            "Missing required setting(s): " + ", ".join(missing),
        )
    return _pass(
        "home_assistant_configuration",
        "Home Assistant configuration",
        "Home Assistant URL and token are configured",
        required=True,
    )


def _check_http_service(
    *,
    check_id: str,
    label: str,
    base_url: str | None,
    timeout_seconds: int,
    headers: dict[str, str] | None = None,
    required: bool,
    path: str = "",
) -> ValidationCheck:
    if not base_url:
        if required:
            return _fail(check_id, label, f"{label} URL is not configured")
        return _warn(check_id, label, f"{label} URL is not configured")

    target = base_url.rstrip("/") + path
    try:
        response = requests.get(
            target,
            headers=headers,
            timeout=max(1, timeout_seconds),
            verify=False,
        )
        if response.status_code < 500:
            return _pass(
                check_id,
                label,
                f"Reachable at {target} (HTTP {response.status_code})",
                required=required,
            )
        message = f"{label} returned HTTP {response.status_code} at {target}"
    except requests.RequestException as exc:
        message = f"Unable to reach {target}: {exc}"

    if required:
        return _fail(check_id, label, message)
    return _warn(check_id, label, message)


def _check_home_assistant_reachability() -> ValidationCheck:
    token = str(CONFIG.get("home_assistant_token") or "")
    return _check_http_service(
        check_id="home_assistant_reachability",
        label="Home Assistant",
        base_url=CONFIG.get("home_assistant_url"),
        timeout_seconds=min(int(CONFIG.get("home_assistant_timeout_seconds", 10)), 5),
        headers={"Authorization": f"Bearer {token}"},
        required=False,
        path="/api/",
    )


def _check_wled_reachability() -> ValidationCheck:
    return _check_http_service(
        check_id="wled_reachability",
        label="WLED controller",
        base_url=CONFIG.get("wled_base_url"),
        timeout_seconds=3,
        required=False,
        path="/json/info",
    )


def _check_airnow_configuration() -> ValidationCheck:
    key = str(CONFIG.get("airnow_api_key") or "").strip()
    zip_code = str(CONFIG.get("airnow_zip") or "").strip()
    if not key and not zip_code:
        return _warn(
            "airnow_configuration",
            "AirNow configuration",
            "AirNow is not configured; outdoor AQI will be unavailable",
        )
    if not key or not zip_code:
        missing = "AIRNOW_API_KEY" if not key else "AIRNOW_ZIP"
        return _warn(
            "airnow_configuration",
            "AirNow configuration",
            f"Partial AirNow configuration; missing {missing}",
        )
    return _pass(
        "airnow_configuration",
        "AirNow configuration",
        "AirNow API key and ZIP code are configured",
        required=False,
    )


def _check_pushover_configuration() -> ValidationCheck:
    if not CONFIG.get("pushover_enabled"):
        return _pass(
            "pushover_configuration", "Pushover alerting",
            "Pushover alert delivery is disabled", required=False,
        )
    missing = [
        name for name, key in (
            ("PUSHOVER_USER_KEY", "pushover_user_key"),
            ("PUSHOVER_API_TOKEN", "pushover_api_token"),
        )
        if not str(CONFIG.get(key) or "").strip()
    ]
    if missing:
        return _warn(
            "pushover_configuration", "Pushover alerting",
            "Alert delivery is waiting for: " + ", ".join(missing),
        )
    return _pass(
        "pushover_configuration", "Pushover alerting",
        "Pushover user key and application token are configured", required=False,
    )


def _check_executable(check_id: str, label: str, configured_path: str, *, enabled: bool = True) -> ValidationCheck:
    if not enabled:
        return _pass(check_id, label, f"{label} is disabled", required=False)

    resolved = shutil.which(configured_path) if os.path.sep not in configured_path else configured_path
    if resolved and Path(resolved).is_file() and os.access(resolved, os.X_OK):
        return _pass(check_id, label, f"Executable available: {resolved}", required=False)
    return _warn(check_id, label, f"Executable not found or not executable: {configured_path}")


def _check_hostname_resolution(url: str | None, check_id: str, label: str) -> ValidationCheck:
    if not url:
        return _warn(check_id, label, f"{label} URL is not configured")
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return _warn(check_id, label, f"Could not determine host from {url}")
    try:
        socket.getaddrinfo(host, parsed.port or 80)
        return _pass(check_id, label, f"Host resolves: {host}", required=False)
    except socket.gaierror as exc:
        return _warn(check_id, label, f"Host does not resolve: {host}: {exc}")


def run_startup_validation(*, include_connectivity: bool = True) -> StartupValidationReport:
    checks: list[ValidationCheck] = [
        _check_env_file(),
        *_check_required_directories(),
        _check_database(),
        _check_peplink_credentials(),
        _check_home_assistant_configuration(),
        _check_airnow_configuration(),
        _check_pushover_configuration(),
        _check_executable(
            "speedtest_executable",
            "Ookla Speedtest",
            str(CONFIG.get("speedtest_path") or "speedtest"),
        ),
        _check_executable(
            "snmpget_executable",
            "SNMP utility",
            str(CONFIG.get("snmpget_path") or "snmpget"),
            enabled=bool(CONFIG.get("snmp_enabled")),
        ),
    ]

    if include_connectivity:
        checks.extend(
            [
                _check_hostname_resolution(
                    CONFIG.get("home_assistant_url"),
                    "home_assistant_resolution",
                    "Home Assistant",
                ),
                _check_home_assistant_reachability(),
                _check_wled_reachability(),
            ]
        )

    fatal_count = sum(check.status == "fail" for check in checks)
    warning_count = sum(check.status == "warning" for check in checks)
    return StartupValidationReport(
        ok=fatal_count == 0,
        fatal_count=fatal_count,
        warning_count=warning_count,
        checks=tuple(checks),
    )


def format_startup_report(report: StartupValidationReport) -> str:
    symbols = {"pass": "PASS", "warning": "WARN", "fail": "FAIL"}
    lines = ["RC-001 startup validation"]
    for check in report.checks:
        lines.append(f"[{symbols[check.status]}] {check.label}: {check.message}")
    lines.append(
        "Startup validation result: "
        + ("PASS" if report.ok else "FAIL")
        + f" ({report.fatal_count} fatal, {report.warning_count} warning)"
    )
    return "\n".join(lines)


def validate_or_raise(*, include_connectivity: bool = True) -> StartupValidationReport:
    report = run_startup_validation(include_connectivity=include_connectivity)
    print(format_startup_report(report), flush=True)
    if not report.ok:
        raise StartupValidationError(report)
    return report
