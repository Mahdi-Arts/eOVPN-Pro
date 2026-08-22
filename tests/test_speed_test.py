"""
eOVPN-Pro Speed & Latency Test Unit Tests
تست‌های واحد مربوط به ماژول پینگ و تست سرعت سرورها در eOVPN-Pro
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from eovpn.speed_test import parse_ovpn_remote, ping_host, test_single_ovpn


class TestSpeedTest(unittest.TestCase):
    """
    Unit tests for configuration endpoint parsing and socket latency testing.
    تست‌های اعتبارسنجی استخراج آدرس سرورها و محاسبه پینگ سوکت TCP.
    """

    def test_parse_ovpn_remote(self):
        test_file = "test_config.ovpn"
        with open(test_file, "w") as f:
            f.write("# comment line\n")
            f.write("remote 127.0.0.1 443 tcp\n")
            f.write("remote example.com 8080\n")
            f.write("remote fallback.net\n")

        remotes = parse_ovpn_remote(test_file)
        if os.path.exists(test_file):
            os.remove(test_file)

        self.assertEqual(len(remotes), 3)
        self.assertEqual(remotes[0], ("127.0.0.1", 443))
        self.assertEqual(remotes[1], ("example.com", 8080))
        self.assertEqual(remotes[2], ("fallback.net", 1194))

    @patch("socket.create_connection")
    def test_ping_host_success(self, mock_create_connection):
        mock_sock = MagicMock()
        mock_create_connection.return_value = mock_sock

        rtt = ping_host("127.0.0.1", 80, timeout=2.0)
        self.assertIsNotNone(rtt)
        self.assertGreaterEqual(rtt or 0.0, 0)
        mock_create_connection.assert_called_once_with(("127.0.0.1", 80), timeout=2.0)
        mock_sock.close.assert_called_once()

    @patch("socket.create_connection")
    def test_ping_host_fail(self, mock_create_connection):
        mock_create_connection.side_effect = TimeoutError("Connection timed out")

        rtt = ping_host("192.0.2.1", 12345, timeout=0.5)
        self.assertIsNone(rtt)

    @patch("eovpn.speed_test.ping_host")
    def test_single_ovpn(self, mock_ping):
        test_file = "test_multi.ovpn"
        with open(test_file, "w") as f:
            f.write("remote s1.example.com 1194\n")
            f.write("remote s2.example.com 1194\n")

        mock_ping.side_effect = [120.5, 45.2]
        best_rtt = test_single_ovpn(test_file, timeout=1.0)
        if os.path.exists(test_file):
            os.remove(test_file)

        self.assertEqual(best_rtt, 45.2)


if __name__ == "__main__":
    unittest.main()
