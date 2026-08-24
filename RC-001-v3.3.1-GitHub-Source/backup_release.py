from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from config import BASE_DIR, CONFIG


DEFAULT_EXCLUDES = {
    ".venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    "backups",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_project_files(root: Path, database_path: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in DEFAULT_EXCLUDES for part in relative.parts):
            continue
        if path.resolve() == database_path.resolve():
            continue
        if path.name.endswith((".pyc", ".swp", "~")):
            continue
        yield path


def _snapshot_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source, timeout=15) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)


def create_backup(output_directory: Path, label: str | None = None) -> Path:
    root = BASE_DIR.resolve()
    database_path = Path(CONFIG["database"]).resolve()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = f"-{label}" if label else ""
    archive_path = output_directory / f"rc001-backup-{timestamp}{suffix}.tar.gz"
    output_directory.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="rc001-backup-") as temporary:
        staging = Path(temporary) / "RC-001-backup"
        project_stage = staging / "project"
        project_stage.mkdir(parents=True)

        copied: list[dict[str, object]] = []
        for source in _iter_project_files(root, database_path):
            relative = source.relative_to(root)
            destination = project_stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(
                {
                    "path": str(Path("project") / relative),
                    "size": destination.stat().st_size,
                    "sha256": _sha256(destination),
                }
            )

        if database_path.is_file():
            db_destination = staging / "database" / database_path.name
            _snapshot_database(database_path, db_destination)
            copied.append(
                {
                    "path": str(Path("database") / database_path.name),
                    "size": db_destination.stat().st_size,
                    "sha256": _sha256(db_destination),
                    "sqlite_snapshot": True,
                }
            )

        manifest = {
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "hostname": os.uname().nodename,
            "source": str(root),
            "database_source": str(database_path),
            "file_count": len(copied),
            "files": copied,
        }
        manifest_path = staging / "BACKUP_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(staging, arcname=staging.name)

    os.chmod(archive_path, 0o600)
    return archive_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a safe RC-001 release backup")
    parser.add_argument(
        "--output",
        type=Path,
        default=BASE_DIR / "backups" / "releases",
        help="Backup output directory",
    )
    parser.add_argument("--label", help="Optional short label appended to the archive name")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        archive = create_backup(args.output.expanduser().resolve(), args.label)
    except Exception as exc:
        print(f"Backup failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Backup created: {archive}")
    print(f"Size: {archive.stat().st_size:,} bytes")
    print("Permissions: owner read/write only (0600)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
