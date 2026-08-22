"""
Offline smoke tests for pure, import-safe modules.
تست‌های دود آفلاین برای ماژول‌های خالص و قابل ایمپورت بدون GTK.
"""

import importlib
import unittest


class TestSmokeImports(unittest.TestCase):
    """Ensure pure modules can always be imported in CI."""

    def test_utils_imports(self):
        module = importlib.import_module("eovpn.utils")
        self.assertTrue(hasattr(module, "download_remote_to_destination"))

    def test_auto_connect_imports(self):
        module = importlib.import_module("eovpn.auto_connect")
        self.assertTrue(hasattr(module, "build_cascade_queue"))

    def test_cascade_imports(self):
        module = importlib.import_module("eovpn.cascade")
        self.assertTrue(hasattr(module, "cascade_progress_fraction"))

    def test_speed_test_imports(self):
        module = importlib.import_module("eovpn.speed_test")
        self.assertTrue(hasattr(module, "test_all_configs"))


if __name__ == "__main__":
    unittest.main()
