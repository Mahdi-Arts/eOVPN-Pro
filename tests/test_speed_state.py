"""Offline tests for session-scoped speed-test measurements."""

import unittest

from eovpn.speed_state import SpeedTestSnapshot
from eovpn.utils import matches_server_filter


class TestSpeedTestSnapshot(unittest.TestCase):
    def test_replace_keeps_measurements_independent_of_projection(self):
        snapshot = SpeedTestSnapshot()
        generation = snapshot.replace({"tcp.ovpn": 42.5, "udp.ovpn": None})

        self.assertEqual(generation, 1)
        self.assertEqual(snapshot.get("tcp.ovpn").latency_ms, 42.5)
        self.assertEqual(snapshot.get("tcp.ovpn").status, "measured")
        self.assertEqual(snapshot.get("udp.ovpn").status, "unreachable")
        self.assertEqual(snapshot.latency_map(), {"tcp.ovpn": 42.5, "udp.ovpn": None})

    def test_next_run_increments_generation(self):
        snapshot = SpeedTestSnapshot()
        snapshot.replace({"a.ovpn": 10})
        first = snapshot.get("a.ovpn")
        snapshot.replace({"a.ovpn": 20})
        second = snapshot.get("a.ovpn")

        self.assertEqual(snapshot.generation, 2)
        self.assertEqual(first.test_generation, 1)
        self.assertEqual(second.test_generation, 2)
        self.assertNotEqual(first.measured_at, second.measured_at)

    def test_measurements_mapping_is_a_copy(self):
        snapshot = SpeedTestSnapshot()
        snapshot.replace({"a.ovpn": 10})
        external = snapshot.measurements
        external.clear()
        self.assertIsNotNone(snapshot.get("a.ovpn"))

    def test_filter_projection_does_not_erase_speed_results(self):
        snapshot = SpeedTestSnapshot()
        snapshot.replace({"tcp.ovpn": 25.0, "udp.ovpn": 40.0})
        original = snapshot.latency_map()

        visible = [
            name
            for name, protocols in {
                "tcp.ovpn": {"tcp"},
                "udp.ovpn": {"udp"},
            }.items()
            if matches_server_filter(
                name,
                mode="all",
                latencies=snapshot.latency_map(),
                proto_mode="tcp",
                protocols=protocols,
            )
        ]

        self.assertEqual(visible, ["tcp.ovpn"])
        self.assertEqual(snapshot.latency_map(), original)


if __name__ == "__main__":
    unittest.main()
