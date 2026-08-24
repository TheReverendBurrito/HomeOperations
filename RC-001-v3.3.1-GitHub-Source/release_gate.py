from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backup_release import create_backup
from config import BASE_DIR
from release_info import get_build_information, get_release_metadata
from selftest import run_self_test


EXPECTED_PROJECT_FRAGMENT = "RC-001-v2.1.0-Security-Operations"


@dataclass(frozen=True)
class GateCheck:
    check_id: str
    label: str
    status: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run_command(command: list[str], timeout: int = 15) -> tuple[int, str, str]:
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return process.returncode, process.stdout.strip(), process.stderr.strip()


def _service_path_check() -> GateCheck:
    code, stdout, stderr = _run_command(
        [
            "systemctl",
            "show",
            "rc001",
            "--property=WorkingDirectory",
            "--property=ExecStart",
            "--no-pager",
        ]
    )
    if code != 0:
        return GateCheck(
            "service_path",
            "Active systemd service path",
            "warning",
            stderr or "Unable to query rc001.service",
        )

    if EXPECTED_PROJECT_FRAGMENT not in stdout:
        return GateCheck(
            "service_path",
            "Active systemd service path",
            "fail",
            "rc001.service is not pointing to the v2.1.0 Security Operations directory",
        )

    return GateCheck(
        "service_path",
        "Active systemd service path",
        "pass",
        "rc001.service is using the v2.1.0 Security Operations deployment",
    )


def _service_state_check() -> GateCheck:
    code, stdout, stderr = _run_command(
        ["systemctl", "is-active", "rc001"]
    )
    state = stdout or stderr or "unknown"
    if code != 0 or state != "active":
        return GateCheck(
            "service_state",
            "RC-001 service state",
            "fail",
            f"rc001.service state is {state}",
        )
    return GateCheck(
        "service_state",
        "RC-001 service state",
        "pass",
        "rc001.service is active",
    )


def _release_metadata_check() -> GateCheck:
    release = get_release_metadata()
    build = get_build_information()
    version = str(release.get("version") or "")
    build_number = str(build.get("build") or "")
    if not version or not build_number:
        return GateCheck(
            "release_metadata",
            "Release metadata",
            "fail",
            "Version or build number is missing",
        )
    return GateCheck(
        "release_metadata",
        "Release metadata",
        "pass",
        f"{version} build {build_number}",
    )


def _backup_capability_check(create_archive: bool) -> tuple[GateCheck, str | None]:
    if not create_archive:
        with tempfile.TemporaryDirectory(prefix="rc001-gate-backup-") as temporary:
            archive = create_backup(Path(temporary), "rc1-readiness-test")
            if not archive.is_file() or archive.stat().st_size == 0:
                return (
                    GateCheck(
                        "backup_capability",
                        "Release backup capability",
                        "fail",
                        "Backup test did not create a valid archive",
                    ),
                    None,
                )
        return (
            GateCheck(
                "backup_capability",
                "Release backup capability",
                "pass",
                "Temporary backup and SQLite snapshot completed successfully",
            ),
            None,
        )

    archive = create_backup(
        BASE_DIR / "backups" / "releases",
        "pre-rc1-readiness",
    )
    return (
        GateCheck(
            "backup_capability",
            "Release backup capability",
            "pass",
            f"Persistent pre-RC1 backup created: {archive}",
        ),
        str(archive),
    )


def run_gate(*, create_archive: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    checks: list[GateCheck] = []

    checks.append(_service_path_check())
    checks.append(_service_state_check())
    checks.append(_release_metadata_check())

    self_test = run_self_test(
        include_connectivity=True,
        check_local_api=True,
    )
    checks.append(
        GateCheck(
            "self_test",
            "Full RC-001 self-test",
            "pass" if self_test.ok else "fail",
            (
                f"{self_test.passed} passed, "
                f"{self_test.warnings} warning, "
                f"{self_test.failed} failed"
            ),
        )
    )

    try:
        backup_check, archive_path = _backup_capability_check(create_archive)
    except Exception as exc:
        backup_check = GateCheck(
            "backup_capability",
            "Release backup capability",
            "fail",
            f"{type(exc).__name__}: {exc}",
        )
        archive_path = None
    checks.append(backup_check)

    failed = sum(check.status == "fail" for check in checks)
    warnings = sum(check.status == "warning" for check in checks)
    passed = sum(check.status == "pass" for check in checks)

    release = get_release_metadata()
    build = get_build_information()
    ready = failed == 0

    report = {
        "product": release.get("product", "RC-001"),
        "version": release.get("version", "unknown"),
        "build": build.get("build", "unknown"),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ready_for_rc1": ready,
        "passed": passed,
        "warnings": warnings,
        "failed": failed,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "backup_archive": archive_path,
        "checks": [check.to_dict() for check in checks],
        "self_test": self_test.to_dict(),
    }
    return report


def format_report(report: dict[str, Any]) -> str:
    status_map = {"pass": "PASS", "warning": "WARN", "fail": "FAIL"}
    lines = [
        "RC-001 Release Candidate Readiness Gate",
        "=" * 72,
        f"Version: {report['version']}",
        f"Build:   {report['build']}",
        "",
    ]
    for check in report["checks"]:
        lines.append(
            f"[{status_map[check['status']]}] "
            f"{check['label']}: {check['message']}"
        )
    lines.extend(
        [
            "",
            "-" * 72,
            f"Result: {'READY FOR RC1' if report['ready_for_rc1'] else 'NOT READY'}",
            (
                f"Checks: {report['passed']} passed, "
                f"{report['warnings']} warning, "
                f"{report['failed']} failed"
            ),
            f"Duration: {report['duration_ms']} ms",
        ]
    )
    if report.get("backup_archive"):
        lines.append(f"Backup: {report['backup_archive']}")
    return "\n".join(lines)


def _write_report(report: dict[str, Any], output: Path | None) -> Path:
    if output is None:
        output = (
            BASE_DIR
            / "backups"
            / "release-reports"
            / f"rc1-readiness-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(output, 0o600)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate whether RC-001 v2.1.0 is ready for RC1 promotion"
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument(
        "--create-backup",
        action="store_true",
        help="Create a persistent pre-RC1 backup instead of a temporary backup test",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the JSON readiness report",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_gate(create_archive=args.create_backup)
    report_path = _write_report(report, args.output)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_report(report))
        print(f"Report: {report_path}")

    return 0 if report["ready_for_rc1"] else 1


if __name__ == "__main__":
    sys.exit(main())
