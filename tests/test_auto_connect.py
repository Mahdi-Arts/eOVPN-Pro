"""
eOVPN-Pro Cascading Auto-Connect Unit Tests
تست‌های واحد موتور اتصال آبشاری و پارس پروتکل TCP/UDP
"""

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
    def __init__(self, names):
        self._rows = [_FakeRow(name) for name in names]

    def get_row_at_index(self, index):
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None


class TestProtoParsing(unittest.TestCase):
    def test_normalize_proto_variants(self):
        self.assertEqual(normalize_proto("tcp"), PROTO_TCP)
        self.assertEqual(normalize_proto("TCP4"), PROTO_TCP)
        self.assertEqual(normalize_proto("tcp-client"), PROTO_TCP)
        self.assertEqual(normalize_proto("udp6"), PROTO_UDP)
        self.assertIsNone(normalize_proto("icmp"))
        self.assertIsNone(normalize_proto(None))

    def test_parse_file_level_proto_and_remote_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mixed.ovpn")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# comment\n")
                handle.write("proto udp\n")
                handle.write("remote 10.0.0.1 1194\n")
                handle.write("remote 10.0.0.2 443 tcp\n")
                handle.write("remote edge.example 1194 udp4\n")
            endpoints = parse_ovpn_endpoints(path)
            self.assertEqual(endpoints[0], ("10.0.0.1", 1194, PROTO_UDP))
            self.assertEqual(endpoints[1], ("10.0.0.2", 443, PROTO_TCP))
            self.assertEqual(endpoints[2], ("edge.example", 1194, PROTO_UDP))
            self.assertEqual(parse_ovpn_protocols(path), frozenset({PROTO_TCP, PROTO_UDP}))

    def test_default_proto_is_udp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "plain.ovpn")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("remote vpn.example\n")
            endpoints = parse_ovpn_endpoints(path)
            self.assertEqual(endpoints, [("vpn.example", 1194, DEFAULT_OVPN_PROTO)])
            self.assertEqual(parse_ovpn_protocols(path), frozenset({PROTO_UDP}))

    def test_tcp_only_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tcp.ovpn")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("proto tcp\n")
                handle.write("remote 192.0.2.10 443\n")
            self.assertEqual(parse_ovpn_protocols(path), frozenset({PROTO_TCP}))

    def test_missing_file_returns_empty(self):
        self.assertEqual(parse_ovpn_protocols("/tmp/does-not-exist-eovpn.ovpn"), frozenset())


class TestTimeoutAndQueue(unittest.TestCase):
    def test_timeout_unknown_and_invalid(self):
        self.assertEqual(compute_attempt_timeout(None), UNKNOWN_RTT_TIMEOUT_SECONDS)
        self.assertEqual(compute_attempt_timeout(-5), UNKNOWN_RTT_TIMEOUT_SECONDS)
        self.assertEqual(
            compute_attempt_timeout("bad"),  # type: ignore[arg-type]  # deliberate robustness test
            UNKNOWN_RTT_TIMEOUT_SECONDS,
        )

    def test_timeout_clamped_to_floor_and_ceiling(self):
        low = compute_attempt_timeout(1.0)
        high = compute_attempt_timeout(5000.0)
        self.assertGreaterEqual(low, MIN_ATTEMPT_TIMEOUT_SECONDS)
        self.assertLessEqual(high, MAX_ATTEMPT_TIMEOUT_SECONDS)
        self.assertLess(compute_attempt_timeout(40.0), compute_attempt_timeout(800.0))

    def test_queue_preserves_visual_order(self):
        visible = ["c.ovpn", "a.ovpn", "b.ovpn"]
        self.assertEqual(build_cascade_queue(visible, {}), visible)

    def test_queue_skips_unreachable_when_any_rtt_exists(self):
        visible = ["fast.ovpn", "dead.ovpn", "ok.ovpn"]
        latencies = {"fast.ovpn": 40.0, "dead.ovpn": None, "ok.ovpn": 90.0}
        self.assertEqual(
            build_cascade_queue(visible, latencies),
            ["fast.ovpn", "ok.ovpn"],
        )

    def test_queue_fallback_when_everything_unreachable(self):
        visible = ["a.ovpn", "b.ovpn"]
        latencies = {"a.ovpn": None, "b.ovpn": None, "hidden.ovpn": 12.0}
        # Visible servers are all dead; still honour the user's filtered list.
        self.assertEqual(build_cascade_queue(visible, latencies), visible)

    def test_queue_respects_max_candidates(self):
        visible = [f"s{i}.ovpn" for i in range(80)]
        queue = build_cascade_queue(visible, {}, max_candidates=5)
        self.assertEqual(queue, visible[:5])

    def test_queue_default_cap(self):
        visible = [f"s{i}.ovpn" for i in range(MAX_CASCADE_CANDIDATES + 10)]
        self.assertEqual(len(build_cascade_queue(visible, {})), MAX_CASCADE_CANDIDATES)

    def test_collect_visible_filenames(self):
        box = _FakeListBox(["one.ovpn", "two.ovpn"])
        self.assertEqual(collect_visible_filenames(box), ["one.ovpn", "two.ovpn"])
        self.assertEqual(collect_visible_filenames(None), [])

    def test_proto_badge(self):
        self.assertEqual(format_proto_badge({PROTO_TCP}), "TCP")
        self.assertEqual(format_proto_badge({PROTO_UDP}), "UDP")
        self.assertEqual(format_proto_badge({PROTO_TCP, PROTO_UDP}), "TCP/UDP")
        self.assertEqual(format_proto_badge(set()), "")
        self.assertEqual(proto_badge_css({PROTO_TCP}), "proto-tcp")
        self.assertEqual(proto_badge_css({PROTO_UDP}), "proto-udp")
        self.assertEqual(proto_badge_css({PROTO_TCP, PROTO_UDP}), "proto-both")


class TestProtoFilterPredicate(unittest.TestCase):
    def test_tcp_filter(self):
        self.assertTrue(
            matches_server_filter("a.ovpn", proto_mode="tcp", protocols={PROTO_TCP})
        )
        self.assertFalse(
            matches_server_filter("b.ovpn", proto_mode="tcp", protocols={PROTO_UDP})
        )

    def test_udp_filter_with_mixed(self):
        self.assertTrue(
            matches_server_filter(
                "mix.ovpn", proto_mode="udp", protocols={PROTO_TCP, PROTO_UDP}
            )
        )

    def test_proto_and_search_combined(self):
        self.assertFalse(
            matches_server_filter(
                "de-tcp.ovpn",
                search="us",
                proto_mode="tcp",
                protocols={PROTO_TCP},
            )
        )
        self.assertTrue(
            matches_server_filter(
                "de-tcp.ovpn",
                search="de",
                proto_mode="tcp",
                protocols={PROTO_TCP},
            )
        )


if __name__ == "__main__":
    unittest.main()
