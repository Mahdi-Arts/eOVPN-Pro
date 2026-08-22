"""Transactional repository tests / تست مخزن تراکنشی کانفیگ."""

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from eovpn.config_import import NoConfigurationsError
from eovpn.config_repository import ConfigRepository, ImportInProgressError


class TestConfigRepository(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "CONFIGS"
        self.repository = ConfigRepository(self.root)
        self.repository.ensure()

    def tearDown(self):
        self.temporary.cleanup()

    def _archive(self, entries, name="source.zip"):
        path = self.base / name
        with zipfile.ZipFile(path, "w") as archive:
            for filename, content in entries:
                archive.writestr(filename, content)
        return path

    def test_success_replaces_old_repository(self):
        old = self.root / "old.ovpn"
        old.write_text("remote old 1\n", encoding="utf-8")
        source = self._archive([("new.ovpn", "remote new 2\n")])
        result = self.repository.update(str(source))
        self.assertEqual(result.configs, ("new.ovpn",))
        self.assertFalse(old.exists())
        self.assertTrue((self.root / "new.ovpn").exists())
        self.assertFalse(list(self.base.glob(".eovpn-*.staging")))
        self.assertFalse(list(self.base.glob(".eovpn-*.backup")))

    def test_validation_failure_preserves_old_repository(self):
        old = self.root / "old.ovpn"
        old.write_text("remote old 1\n", encoding="utf-8")
        source = self._archive([("README.txt", "empty")], "empty.zip")
        with self.assertRaises(NoConfigurationsError):
            self.repository.update(str(source))
        self.assertEqual(old.read_text(encoding="utf-8"), "remote old 1\n")

    def test_second_rename_failure_rolls_back(self):
        old = self.root / "old.ovpn"
        old.write_text("remote old 1\n", encoding="utf-8")
        source = self._archive([("new.ovpn", "remote new 2\n")])
        real_replace = os.replace
        calls = 0

        def controlled_replace(source_path, destination_path):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated install rename failure")
            return real_replace(source_path, destination_path)

        with patch("eovpn.config_repository.os.replace", side_effect=controlled_replace):
            with self.assertRaises(OSError):
                self.repository.update(str(source))
        self.assertTrue(old.exists())
        self.assertFalse((self.root / "new.ovpn").exists())

    def test_concurrent_update_is_rejected(self):
        source = self._archive([("new.ovpn", "remote new 2\n")])
        self.repository._lock.acquire()
        self.addCleanup(self.repository._lock.release)
        with self.assertRaises(ImportInProgressError):
            self.repository.update(str(source))


if __name__ == "__main__":
    unittest.main()
