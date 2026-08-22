"""TCP latency semantics tests / تست معنای سنجش تأخیر TCP."""

import math
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from eovpn.speed_test import (
    parse_ovpn_remote,
    ping_host,
    test_all_configs,
    test_single_ovpn,
)


class TestSpeedTest(unittest.TestCase):
    def _config(self, content, name="test.ovpn"):
        directory = tempfile.TemporaryDirectory()
        path = os.path.join(directory.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        self.addCleanup(directory.cleanup)
        return directory.name, path

    def test_parse_remote_uses_shared_parser(self):
        _directory, path = self._config(
            "proto tcp\nremote 127.0.0.1 443\nremote fallback.example\n"
        )
        self.assertEqual(
            parse_ovpn_remote(path),
            [("127.0.0.1", 443), ("fallback.example", 1194)],
        )

    @patch("socket.create_connection")
    def test_ping_success_closes_context(self, create_connection):
        socket_context = MagicMock()
        create_connection.return_value = socket_context
        result = ping_host("127.0.0.1", 80, timeout=2.0)
        self.assertIsNotNone(result)
        create_connection.assert_called_once_with(("127.0.0.1", 80), timeout=2.0)
        socket_context.__exit__.assert_called_once()

    @patch("socket.create_connection", side_effect=ConnectionRefusedError)
    def test_refused_connection_is_reachable(self, _create_connection):
        self.assertIsNotNone(ping_host("127.0.0.1", 9))

    @patch("socket.create_connection", side_effect=TimeoutError)
    def test_timeout_is_unreachable(self, _create_connection):
        self.assertIsNone(ping_host("192.0.2.1", 12345, timeout=0.1))

    @patch("eovpn.speed_test.ping_host", side_effect=[120.5, 45.2])
    def test_best_tcp_endpoint(self, _ping):
        _directory, path = self._config(
            "proto tcp\nremote s1.example 1194\nremote s2.example 443\n"
        )
        self.assertEqual(test_single_ovpn(path), 45.2)

    @patch("eovpn.speed_test.ping_host", return_value=None)
    def test_attempted_tcp_failure_is_infinity(self, _ping):
        _directory, path = self._config("proto tcp\nremote dead.example 443\n")
        self.assertTrue(math.isinf(test_single_ovpn(path)))

    @patch("eovpn.speed_test.ping_host")
    def test_udp_only_is_unmeasured_without_tcp_probe(self, ping):
        _directory, path = self._config("proto udp\nremote udp.example 1194\n")
        self.assertIsNone(test_single_ovpn(path))
        ping.assert_not_called()

    @patch("eovpn.speed_test.test_single_ovpn", return_value=12.0)
    def test_all_rejects_traversal_and_non_config_names(self, single):
        directory, _path = self._config("proto tcp\nremote one 443\n", "safe.ovpn")
        results = test_all_configs(
            directory,
            ["safe.ovpn", "../safe.ovpn", "note.txt", "missing.ovpn"],
            max_workers=100,
        )
        self.assertEqual(results, {"safe.ovpn": 12.0})
        single.assert_called_once()


if __name__ == "__main__":
    unittest.main()
