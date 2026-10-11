"""Offline tests for language action value handling."""

import unittest

from gi.repository import GLib

from eovpn.main_window import normalize_language_value


class TestLanguageState(unittest.TestCase):
    def test_supported_variant_values(self):
        self.assertEqual(normalize_language_value(GLib.Variant("s", "fa")), "fa")
        self.assertEqual(normalize_language_value(GLib.Variant("s", "en")), "en")

    def test_unsupported_and_malformed_values_are_rejected(self):
        self.assertIsNone(normalize_language_value(GLib.Variant("s", "de")))
        self.assertIsNone(normalize_language_value(None))
        self.assertIsNone(normalize_language_value("'invalid'"))


if __name__ == "__main__":
    unittest.main()
