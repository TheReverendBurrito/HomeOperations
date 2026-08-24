from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import requests

from config import BASE_DIR, CONFIG
from release_info import get_build_information, get_release_metadata
from startup_validation import run_startup_validation


@dataclass(frozen=True)
class SelfTestCheck:
    check_id: str
    label: str
    status: str
    message: str
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfTestReport:
    ok: bool
    passed: int
    warnings: int
    failed: int
    duration_ms: int
    checks: tuple[SelfTestCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "passed": self.passed,
            "warnings": self.warnings,
            "failed": self.failed,
            "duration_ms": self.duration_ms,
            "checks": [check.to_dict() for check in self.checks],
        }


def _timed_check(
    check_id: str,
    label: str,
    function: Callable[[], tuple[str, str]],
) -> SelfTestCheck:
    started = time.monotonic()
    try:
        status, message = function()
    except Exception as exc:  # keep the diagnostic utility running
        status, message = "fail", f"{type(exc).__name__}: {exc}"
    duration_ms = round((time.monotonic() - started) * 1000)
    return SelfTestCheck(check_id, label, status, message, duration_ms)


def _metadata_check() -> tuple[str, str]:
    required = ("VERSION.json", "MANIFEST.json", "BUILD_INFO.json")
    missing = [name for name in required if not (BASE_DIR / name).is_file()]
    if missing:
        return "fail", "Missing release metadata: " + ", ".join(missing)
    release = get_release_metadata()
    build = get_build_information()
    return (
        "pass",
        f"{release.get('product', 'RC-001')} {release.get('version', 'unknown')} "
        f"build {build.get('build', 'unknown')}",
    )


def _database_integrity_check() -> tuple[str, str]:
    database_path = Path(CONFIG["database"])
    if not database_path.is_file():
        return "fail", f"Database does not exist: {database_path}"
    with sqlite3.connect(database_path, timeout=10) as connection:
        result = connection.execute("PRAGMA quick_check").fetchone()
    value = str(result[0] if result else "unknown")
    if value.lower() != "ok":
        return "fail", f"SQLite quick_check returned: {value}"
    return "pass", f"SQLite integrity check passed: {database_path}"


def _ring_check() -> tuple[str, str]:
    from ring_service import collect_ring_status

    payload = collect_ring_status(log_changes=False)
    cameras = payload.get("cameras") or []
    if not payload.get("available"):
        return "warning", payload.get("error") or "Ring/Home Assistant data unavailable"
    online = sum(bool(camera.get("available")) for camera in cameras)
    total = len(cameras)
    if total == 0:
        return "warning", "No Ring cameras were returned"
    return "pass", f"Ring camera telemetry available: {online}/{total} cameras online"


def _local_api_check() -> tuple[str, str]:
    endpoints = ("/api/build", "/api/status", "/api/security/cameras", "/api/alerts")
    failures: list[str] = []
    for endpoint in endpoints:
        try:
            response = requests.get(f"http://127.0.0.1:5050{endpoint}", timeout=8)
            if response.status_code >= 400:
                failures.append(f"{endpoint}=HTTP {response.status_code}")
        except requests.RequestException as exc:
            failures.append(f"{endpoint}={exc}")
    if failures:
        return "warning", "Local API unavailable or unhealthy: " + "; ".join(failures)
    return "pass", "Core local API endpoints returned successfully"


def run_self_test(*, include_connectivity: bool = True, check_local_api: bool = True) -> SelfTestReport:
    started = time.monotonic()
    checks: list[SelfTestCheck] = []

    startup_report = run_startup_validation(include_connectivity=include_connectivity)
    for item in startup_report.checks:
        checks.append(
            SelfTestCheck(
                check_id=f"startup_{item.check_id}",
                label=item.label,
                status=item.status,
                message=item.message,
                duration_ms=0,
            )
        )

    checks.append(_timed_check("release_metadata", "Release metadata", _metadata_check))
    checks.append(_timed_check("database_integrity", "Database integrity", _database_integrity_check))

    if include_connectivity:
        checks.append(_timed_check("ring_telemetry", "Ring telemetry", _ring_check))
        if check_local_api:
            checks.append(_timed_check("local_api", "Local API", _local_api_check))

    passed = sum(item.status == "pass" for item in checks)
    warnings = sum(item.status == "warning" for item in checks)
    failed = sum(item.status == "fail" for item in checks)
    return SelfTestReport(
        ok=failed == 0,
        passed=passed,
        warnings=warnings,
        failed=failed,
        duration_ms=round((time.monotonic() - started) * 1000),
        checks=tuple(checks),
    )


def format_report(report: SelfTestReport) -> str:
    icons = {"pass": "PASS", "warning": "WARN", "fail": "FAIL"}
    lines = ["RC-001 Self Test", "=" * 64]
    for check in report.checks:
        duration = f" ({check.duration_ms} ms)" if check.duration_ms else ""
        lines.append(f"[{icons[check.status]}] {check.label}: {check.message}{duration}")
    lines.extend(
        [
            "-" * 64,
            f"Result: {'PASS' if report.ok else 'FAIL'}",
            f"Checks: {report.passed} passed, {report.warnings} warning, {report.failed} failed",
            f"Duration: {report.duration_ms} ms",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RC-001 post-install self test")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--skip-connectivity",
        action="store_true",
        help="Skip Home Assistant, Ring, WLED, DNS, and API connectivity checks",
    )
    parser.add_argument(
        "--skip-local-api",
        action="store_true",
        help="Skip calls to the running RC-001 Flask service",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_self_test(
        include_connectivity=not args.skip_connectivity,
        check_local_api=not args.skip_local_api,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
