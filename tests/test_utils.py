"""Pure utility predicate tests / تست توابع خالص کمکی."""

import math
import os
import tempfile
import unittest

from eovpn.utils import is_safe_path, latency_state, matches_server_filter, ovpn_is_auth_required


class TestPathsAndAuthentication(unittest.TestCase):
    def test_safe_path_uses_canonical_common_path(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(is_safe_path(directory, os.path.join(directory, "config.ovpn")))
            self.assertFalse(is_safe_path(directory, os.path.join(directory, "..", "escape")))

    def test_auth_directive_excludes_comments_and_substrings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "test.ovpn")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# auth-user-pass\nsetenv note auth-user-pass\n")
            self.assertFalse(ovpn_is_auth_required(path))
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("AUTH-USER-PASS credentials.txt\n")
            self.assertTrue(ovpn_is_auth_required(path))
        self.assertFalse(ovpn_is_auth_required("/missing/config.ovpn"))


class TestFilterPredicate(unittest.TestCase):
    def test_latency_state(self):
        self.assertEqual(latency_state(10.0), "online")
        self.assertEqual(latency_state(math.inf), "offline")
        self.assertEqual(latency_state(None), "unknown")
        self.assertEqual(latency_state(10.0, measured=False), "unknown")
        self.assertEqual(latency_state("invalid"), "unknown")

    def test_search_and_favorites(self):
        favorites = {"Iran-Tehran.ovpn"}
        self.assertTrue(
            matches_server_filter(
                "Iran-Tehran.ovpn",
                search="tehran",
                mode="favorites",
                favorites=favorites,
            )
        )
        self.assertFalse(
            matches_server_filter(
                "Germany.ovpn",
                search="tehran",
                mode="favorites",
                favorites=favorites,
            )
        )

    def test_status_filter_requires_measurement(self):
        latencies = {"up.ovpn": 42.0, "down.ovpn": math.inf, "udp.ovpn": None}
        self.assertTrue(matches_server_filter("up.ovpn", mode="online", latencies=latencies))
        self.assertTrue(matches_server_filter("down.ovpn", mode="offline", latencies=latencies))
        self.assertFalse(matches_server_filter("udp.ovpn", mode="offline", latencies=latencies))
        self.assertFalse(matches_server_filter("missing.ovpn", mode="online", latencies=latencies))

    def test_protocol_filter(self):
        self.assertTrue(matches_server_filter("a.ovpn", proto_mode="tcp", protocols={"tcp"}))
        self.assertFalse(matches_server_filter("a.ovpn", proto_mode="udp", protocols={"tcp"}))


if __name__ == "__main__":
    unittest.main()
