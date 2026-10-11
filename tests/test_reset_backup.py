"""Offline tests for reset backup safety."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from eovpn.reset_backup import create_reset_backup, latest_reset_backup, load_reset_manifest


class TestResetBackup(unittest.TestCase):
    def test_snapshot_contains_configs_and_non_secret_settings(self):
        with tempfile.TemporaryDirectory() as root:
            config_dir = Path(root) / "eovpn" / "CONFIGS"
            config_dir.mkdir(parents=True)
            (config_dir / "sample.ovpn").write_text("remote vpn.example 1194\n", encoding="utf-8")

            backup = Path(
                create_reset_backup(str(config_dir), {"language": "fa", "favorite-configs": ["sample.ovpn"]})
            )
            self.assertEqual(latest_reset_backup(str(config_dir)), backup)
            self.assertEqual(
                (backup / "config" / "sample.ovpn").read_text(encoding="utf-8"),
                "remote vpn.example 1194\n",
            )
            manifest = load_reset_manifest(str(backup), str(config_dir))
            self.assertFalse(manifest["secret_service_credentials_copied"])
            self.assertEqual(manifest["settings"]["language"], "fa")
            self.assertEqual(os.stat(backup / "manifest.json").st_mode & 0o777, 0o600)

    def test_manifest_rejects_backup_outside_parent(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            config_dir = Path(root) / "eovpn" / "CONFIGS"
            config_dir.mkdir(parents=True)
            external = Path(outside) / "backup"
            external.mkdir()
            (external / "manifest.json").write_text(
                json.dumps({"format": 1, "settings": {}, "secret_service_credentials_copied": False}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_reset_manifest(str(external), str(config_dir))

    def test_manifest_rejects_symlink_backup(self):
        with tempfile.TemporaryDirectory() as root:
            config_dir = Path(root) / "eovpn" / "CONFIGS"
            config_dir.mkdir(parents=True)
            real = config_dir.parent / "reset-backup-real"
            real.mkdir()
            (real / "manifest.json").write_text(
                json.dumps({"format": 1, "settings": {}, "secret_service_credentials_copied": False}),
                encoding="utf-8",
            )
            link = config_dir.parent / "reset-backup-link"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(ValueError):
                load_reset_manifest(str(link), str(config_dir))


if __name__ == "__main__":
    unittest.main()
