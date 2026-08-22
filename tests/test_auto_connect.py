"""Auto-connect and protocol parser tests / تست موتور اتصال و پارسر پروتکل."""

import math
import os
import tempfile
import unittest

from eovpn.auto_connect import (
    DEFAULT_OVPN_PROTO,
    MAX_ATTEMPT_TIMEOUT_SECONDS,
    MAX_CASCADE_CANDIDATES,
    MIN_ATTEMPT_TIMEOUT_SECONDS,
    PROTO_TCP,
    PROTO_UDP,
    UNKNOWN_RTT_TIMEOUT_SECONDS,
    build_cascade_queue,
    collect_visible_filenames,
    compute_attempt_timeout,
    format_proto_badge,
    normalize_proto,
    parse_ovpn_endpoints,
    parse_ovpn_protocols,
    proto_badge_css,
)
from eovpn.utils import matches_server_filter


class _FakeRow:
    def __init__(self, filename):
        self.filename = filename


class _FakeListBox:
    def __init__(self, names, *, fail_at=None):
        self.rows = [_FakeRow(name) for name in names]
        self.fail_at = fail_at

    def get_row_at_index(self, index):
        if index == self.fail_at:
            raise RuntimeError("simulated model disposal")
        return self.rows[index] if 0 <= index < len(self.rows) else None


class TestProtocolParsing(unittest.TestCase):
    def _config(self, content):
        directory = tempfile.TemporaryDirectory()
        path = os.path.join(directory.name, "test.ovpn")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        self.addCleanup(directory.cleanup)
        return path

    def test_normalize_variants(self):
        self.assertEqual(normalize_proto("TCP4"), PROTO_TCP)
        self.assertEqual(normalize_proto("tcp-client"), PROTO_TCP)
        self.assertEqual(normalize_proto("udp6"), PROTO_UDP)
        self.assertIsNone(normalize_proto("icmp"))
        self.assertIsNone(normalize_proto(None))

    def test_file_protocol_applies_even_when_declared_after_remote(self):
        path = self._config(
            "remote 10.0.0.1 1194\n"
            "proto tcp-client\n"
            "remote 10.0.0.2 443 udp4\n"
        )
        self.assertEqual(
            parse_ovpn_endpoints(path),
            [
                ("10.0.0.1", 1194, PROTO_TCP),
                ("10.0.0.2", 443, PROTO_UDP),
            ],
        )

    def test_default_protocol_is_udp(self):
        path = self._config("remote vpn.example\n")
        self.assertEqual(
            parse_ovpn_endpoints(path),
            [("vpn.example", 1194, DEFAULT_OVPN_PROTO)],
        )

    def test_comments_quotes_and_case_are_supported(self):
        path = self._config(
            "; remote ignored.example 1\n"
            "PROTO TCP\n"
            'REMOTE "vpn.example" 443\n'
        )
        self.assertEqual(parse_ovpn_endpoints(path), [("vpn.example", 443, PROTO_TCP)])

    def test_invalid_port_and_malformed_quote_are_ignored(self):
        path = self._config('remote bad.example 70000\nremote "broken\n')
        self.assertEqual(parse_ovpn_endpoints(path), [])

    def test_protocol_set_and_missing_file(self):
        path = self._config("proto tcp\nremote one 443\nremote two 1194 udp\n")
        self.assertEqual(parse_ovpn_protocols(path), frozenset({PROTO_TCP, PROTO_UDP}))
        self.assertEqual(parse_ovpn_protocols("/not/present.ovpn"), frozenset())


class TestTimeoutAndQueue(unittest.TestCase):
    def test_unknown_invalid_and_offline_timeout(self):
        self.assertEqual(compute_attempt_timeout(None), UNKNOWN_RTT_TIMEOUT_SECONDS)
        self.assertEqual(compute_attempt_timeout("bad"), UNKNOWN_RTT_TIMEOUT_SECONDS)
        self.assertEqual(compute_attempt_timeout(-1), UNKNOWN_RTT_TIMEOUT_SECONDS)
        self.assertEqual(compute_attempt_timeout(math.inf), MIN_ATTEMPT_TIMEOUT_SECONDS)

    def test_timeout_is_bounded(self):
        self.assertGreaterEqual(compute_attempt_timeout(1), MIN_ATTEMPT_TIMEOUT_SECONDS)
        self.assertLessEqual(compute_attempt_timeout(5000), MAX_ATTEMPT_TIMEOUT_SECONDS)
        self.assertLess(compute_attempt_timeout(40), compute_attempt_timeout(800))

    def test_queue_preserves_visual_order(self):
        visible = ["c.ovpn", "a.ovpn", "b.ovpn"]
        self.assertEqual(build_cascade_queue(visible, {}), visible)

    def test_queue_skips_only_measured_offline(self):
        visible = ["fast.ovpn", "udp.ovpn", "dead.ovpn", "ok.ovpn"]
        latencies = {
            "fast.ovpn": 40.0,
            "udp.ovpn": None,
            "dead.ovpn": math.inf,
            "ok.ovpn": 90.0,
        }
        self.assertEqual(
            build_cascade_queue(visible, latencies),
            ["fast.ovpn", "udp.ovpn", "ok.ovpn"],
        )

    def test_queue_falls_back_when_every_visible_server_is_offline(self):
        visible = ["a.ovpn", "b.ovpn"]
        latencies = {"a.ovpn": math.inf, "b.ovpn": math.inf, "hidden.ovpn": 12.0}
        self.assertEqual(build_cascade_queue(visible, latencies), visible)

    def test_queue_is_bounded_and_minimum_limit_is_one(self):
        visible = [f"s{i}.ovpn" for i in range(MAX_CASCADE_CANDIDATES + 10)]
        self.assertEqual(len(build_cascade_queue(visible, {})), MAX_CASCADE_CANDIDATES)
        self.assertEqual(build_cascade_queue(visible, {}, max_candidates=0), visible[:1])

    def test_collect_visible_rows_and_disposed_model(self):
        self.assertEqual(
            collect_visible_filenames(_FakeListBox(["one.ovpn", "two.ovpn"])),
            ["one.ovpn", "two.ovpn"],
        )
        self.assertEqual(
            collect_visible_filenames(_FakeListBox(["one.ovpn"], fail_at=0)),
            [],
        )
        self.assertEqual(collect_visible_filenames(None), [])

    def test_protocol_badges(self):
        self.assertEqual(format_proto_badge({PROTO_TCP}), "TCP")
        self.assertEqual(format_proto_badge({PROTO_UDP}), "UDP")
        self.assertEqual(format_proto_badge({PROTO_TCP, PROTO_UDP}), "TCP/UDP")
        self.assertEqual(proto_badge_css({PROTO_TCP}), "proto-tcp")
        self.assertEqual(proto_badge_css({PROTO_UDP}), "proto-udp")
        self.assertEqual(proto_badge_css({PROTO_TCP, PROTO_UDP}), "proto-both")
        self.assertEqual(format_proto_badge(set()), "")


class TestServerFilter(unittest.TestCase):
    def test_search_favorite_and_protocol_compose(self):
        self.assertTrue(
            matches_server_filter(
                "de-tcp.ovpn",
                search="DE",
                mode="favorites",
                favorites={"de-tcp.ovpn"},
                proto_mode="tcp",
                protocols={PROTO_TCP},
            )
        )
        self.assertFalse(
            matches_server_filter(
                "de-tcp.ovpn", search="us", proto_mode="tcp", protocols={PROTO_TCP}
            )
        )

    def test_online_offline_and_unknown_are_distinct(self):
        latencies = {"online.ovpn": 20.0, "offline.ovpn": math.inf, "udp.ovpn": None}
        self.assertTrue(matches_server_filter("online.ovpn", mode="online", latencies=latencies))
        self.assertTrue(matches_server_filter("offline.ovpn", mode="offline", latencies=latencies))
        self.assertFalse(matches_server_filter("udp.ovpn", mode="offline", latencies=latencies))
        self.assertFalse(matches_server_filter("never.ovpn", mode="online", latencies=latencies))


if __name__ == "__main__":
    unittest.main()
