from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from backup_release import create_backup
from config import BASE_DIR
from release_gate import run_gate


TARGET_VERSION = "2.1.0-rc1"
TARGET_VERSION_SHORT = "2.1.0"
TARGET_BUILD = "2026.07.16.002"
TARGET_RELEASE_TYPE = "rc"
TARGET_RELEASE_LABEL = "Release Candidate"
TARGET_CODENAME = "Security Operations"

EXCLUDED_PARTS = {
    ".env",
    ".venv",
    "__pycache__",
    "backups",
    "data",
    ".git",
    ".pytest_cache",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".swp", ".db", ".db-wal", ".db-shm"}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _metadata_payloads() -> dict[str, dict[str, Any]]:
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    version = _load_json(BASE_DIR / "VERSION.json")
    version.update(
        {
            "product": "RC-001",
            "display_name": "Home Operations Center",
            "version": TARGET_VERSION,
            "version_short": TARGET_VERSION_SHORT,
            "build": TARGET_BUILD,
            "release_type": TARGET_RELEASE_TYPE,
            "release_type_label": TARGET_RELEASE_LABEL,
            "codename": TARGET_CODENAME,
            "database_schema": int(version.get("database_schema", 2)),
            "compatible_from": str(version.get("compatible_from", "2.0.0")),
        }
    )

    build = _load_json(BASE_DIR / "BUILD_INFO.json")
    build.update(
        {
            "built_at": now,
            "build_host": "RC-001 Raspberry Pi release promotion",
            "source": "RC-001 v2.1.0 Security Operations",
            "revision": str(build.get("revision", "local")),
            "notes": (
                "Promoted from v2.1.0-beta3 after successful RC1 readiness "
                "validation. No application behavior changes."
            ),
        }
    )

    manifest = _load_json(BASE_DIR / "MANIFEST.json")
    manifest.update(
        {
            "manifest_version": int(manifest.get("manifest_version", 1)),
            "product": "RC-001",
            "release": TARGET_VERSION,
            "build": TARGET_BUILD,
            "component": "Sprint 5.6 RC1 Promotion",
            "frontend_assets_modified": False,
            "database_migration_required": False,
            "restart_required": True,
        }
    )

    return {
        "VERSION.json": version,
        "BUILD_INFO.json": build,
        "MANIFEST.json": manifest,
    }


def _should_include(path: Path) -> bool:
    relative = path.relative_to(BASE_DIR)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    if path.name.startswith("..") or path.name.endswith(".swp"):
        return False
    return path.is_file()


def _create_release_archive(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"RC-001-v{TARGET_VERSION}.zip"
    checksum_path = archive.with_suffix(".sha256")

    included: list[Path] = [
        path for path in sorted(BASE_DIR.rglob("*"))
        if _should_include(path)
    ]

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in included:
            bundle.write(
                path,
                arcname=f"RC-001-v{TARGET_VERSION}/{path.relative_to(BASE_DIR)}",
            )

        manifest_lines = []
        for path in included:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_lines.append(f"{digest}  {path.relative_to(BASE_DIR)}")
        bundle.writestr(
            f"RC-001-v{TARGET_VERSION}/RELEASE_CHECKSUMS.sha256",
            "\n".join(manifest_lines) + "\n",
        )

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum_path.write_text(
        f"{digest}  {archive.name}\n",
        encoding="utf-8",
    )
    os.chmod(archive, 0o600)
    os.chmod(checksum_path, 0o600)
    return archive, checksum_path


def _write_signoff(
    *,
    gate: dict[str, Any],
    backup: Path,
    archive: Path,
    checksum: Path,
) -> Path:
    reports = BASE_DIR / "backups" / "release-reports"
    reports.mkdir(parents=True, exist_ok=True)
    signoff = reports / (
        f"rc1-promotion-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    payload = {
        "product": "RC-001",
        "promotion": {
            "from": gate.get("version"),
            "to": TARGET_VERSION,
            "build": TARGET_BUILD,
            "promoted_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
        "readiness_gate": gate,
        "backup_archive": str(backup),
        "release_archive": str(archive),
        "release_archive_checksum": str(checksum),
        "status": "PROMOTED_TO_RC1",
    }
    _atomic_write_json(signoff, payload)
    os.chmod(signoff, 0o600)
    return signoff


def promote(*, output_dir: Path) -> dict[str, str]:
    gate = run_gate(create_archive=False)
    if not gate.get("ready_for_rc1"):
        raise RuntimeError(
            "RC1 readiness gate failed. Promotion was not performed."
        )

    backup = create_backup(
        BASE_DIR / "backups" / "releases",
        "pre-rc1-promotion",
    )

    metadata_backup_dir = (
        BASE_DIR
        / "backups"
        / f"pre-rc1-metadata-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    metadata_backup_dir.mkdir(parents=True, exist_ok=True)

    payloads = _metadata_payloads()
    for filename, payload in payloads.items():
        current = BASE_DIR / filename
        if current.exists():
            shutil.copy2(current, metadata_backup_dir / filename)
        _atomic_write_json(current, payload)

    archive, checksum = _create_release_archive(output_dir)
    signoff = _write_signoff(
        gate=gate,
        backup=backup,
        archive=archive,
        checksum=checksum,
    )

    return {
        "version": TARGET_VERSION,
        "build": TARGET_BUILD,
        "backup": str(backup),
        "metadata_backup": str(metadata_backup_dir),
        "release_archive": str(archive),
        "checksum": str(checksum),
        "signoff": str(signoff),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote a validated RC-001 beta build to v2.1.0 RC1"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=BASE_DIR / "backups" / "release-candidates",
        help="Directory for the generated RC1 archive",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable output",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = promote(output_dir=args.output_dir)
    except Exception as exc:
        print(f"RC1 promotion failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("RC-001 successfully promoted to Release Candidate 1")
        print("=" * 64)
        print(f"Version:          {result['version']}")
        print(f"Build:            {result['build']}")
        print(f"Backup:           {result['backup']}")
        print(f"Metadata backup:  {result['metadata_backup']}")
        print(f"Release archive:  {result['release_archive']}")
        print(f"Checksum:         {result['checksum']}")
        print(f"Sign-off report:  {result['signoff']}")
        print()
        print("Restart rc001.service to load the RC1 metadata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
