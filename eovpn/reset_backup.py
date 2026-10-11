"""Safe local snapshots for the settings reset workflow."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESET_BACKUP_PREFIX = "reset-backup-"
RESET_BACKUP_FORMAT = 1


def create_reset_backup(config_dir: str, settings: dict[str, Any]) -> str:
    """Create a private, local snapshot before a destructive reset.

    Secret Service credentials are intentionally not copied. Imported
    configuration files may themselves contain sensitive material, so the
    snapshot is protected locally and does not claim that their contents are
    secret-free.
    """
    source = Path(config_dir)
    parent = source.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if source.is_symlink():
        raise ValueError("managed configuration directory must not be a symlink")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = parent / f"{RESET_BACKUP_PREFIX}{timestamp}-{os.getpid()}"
    suffix = 1
    while backup.exists():
        backup = parent / f"{RESET_BACKUP_PREFIX}{timestamp}-{os.getpid()}-{suffix}"
        suffix += 1

    backup.mkdir(mode=0o700)
    try:
        if source.exists():
            shutil.copytree(source, backup / "config", symlinks=True)
        manifest = {
            "format": RESET_BACKUP_FORMAT,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "secret_service_credentials_copied": False,
            "config_secret_content": "unknown",
            "settings": settings,
        }
        manifest_path = backup / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
        )
        os.chmod(manifest_path, 0o600)
    except Exception:
        shutil.rmtree(backup, ignore_errors=True)
        raise
    return str(backup)


def latest_reset_backup(config_dir: str) -> Path | None:
    """Return the newest valid backup beneath the managed config parent."""
    parent = Path(config_dir).parent
    if not parent.is_dir():
        return None
    candidates = []
    for item in parent.iterdir():
        if (
            item.name.startswith(RESET_BACKUP_PREFIX)
            and item.is_dir()
            and not item.is_symlink()
            and (item / "manifest.json").is_file()
        ):
            candidates.append(item)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime_ns)


def load_reset_manifest(backup_dir: str, config_dir: str) -> dict[str, Any]:
    """Load and validate a backup manifest within the managed parent."""
    parent = Path(config_dir).parent.resolve()
    backup_input = Path(backup_dir)
    if backup_input.is_symlink():
        raise ValueError("reset backup directory must not be a symlink")
    backup = backup_input.resolve()
    try:
        backup.relative_to(parent)
    except ValueError as exc:
        raise ValueError("reset backup is outside the managed configuration parent") from exc
    if not backup.is_dir():
        raise ValueError("reset backup directory is unavailable")
    manifest_path = backup / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != RESET_BACKUP_FORMAT:
        raise ValueError("unsupported reset backup format")
    settings = data.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("reset backup settings are invalid")
    return data
