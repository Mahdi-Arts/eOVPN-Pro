"""
eOVPN-Pro Network Monitor Unit Tests
تست‌های واحد مانیتور شبکه eOVPN-Pro

Tests the single-pass ``/proc/net/dev`` reader with mocked file contents and a
fake scheduler — no GTK session required.
خواننده تک‌گذره ``/proc/net/dev`` را با محتوای شبیه‌سازی‌شده و زمان‌بند جعلی تست
می‌کند — بدون نیاز به نشست GTK.
"""

import unittest
from unittest.mock import patch

from eovpn.network_monitor import NetworkMonitor

_SAMPLE_PROC = """\
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo:    1000       0    0    0    0     0          0         0     1000       0    0    0    0     0       0          0
  eth0:    5000       0    0    0    0     0          0         0     3000       0    0    0    0     0       0          0
  tun0:    1000       0    0    0    0     0          0         0      500       0    0    0    0     0       0          0
"""

_SAMPLE_PROC_T2 = """\
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo:    1000       0    0    0    0     0          0         0     1000       0    0    0    0     0       0          0
  eth0:    5000       0    0    0    0     0          0         0     3000       0    0    0    0     0       0          0
  tun0:    2000       0    0    0    0     0          0         0     1000       0    0    0    0     0       0          0
"""


class FakeScheduler:
    """Timer scheduler stub / بدل زمان‌بند."""

    def __init__(self):
        self.removed = []

    def add_timeout(self, interval_ms, callback):
        return "source-id"

    def add_timeout_seconds(self, interval_seconds, callback):
        return "source-id"

    def remove_timeout(self, source_id):
        self.removed.append(source_id)


class _Label:
    """Label callback recorder / ثبت‌کننده فراخوانی برچسب."""

    def __init__(self):
        self.texts = []

    def set_text(self, text: str) -> None:
        self.texts.append(text)


class TestNetworkMonitor(unittest.TestCase):
    """Counter reading and label updates / خواندن شمارنده‌ها و به‌روزرسانی برچسب‌ها."""

    def _make_monitor(self, proc_content: str):
        scheduler = FakeScheduler()
        download = _Label()
        upload = _Label()
        total = _Label()
        monitor = NetworkMonitor(scheduler, download.set_text, upload.set_text, total.set_text)
        return monitor, scheduler, download, upload, total

    def test_read_counters_prefers_vpn_interface(self):
        monitor, _s, _d, _u, _t = self._make_monitor(_SAMPLE_PROC)
        with patch("eovpn.network_monitor.open", unittest.mock.mock_open(read_data=_SAMPLE_PROC)):
            rx, tx, vpn_found = monitor._read_counters()
        self.assertTrue(vpn_found)
        self.assertEqual((rx, tx), (1000, 500))

    def test_read_counters_falls_back_without_vpn_interface(self):
        content = _SAMPLE_PROC.replace("tun0", "wlan0")
        monitor, _s, _d, _u, _t = self._make_monitor(content)
        with patch("eovpn.network_monitor.open", unittest.mock.mock_open(read_data=content)):
            rx, tx, vpn_found = monitor._read_counters()
        self.assertFalse(vpn_found)
        # wlan0 + eth0 (lo excluded) / جمع wlan0 و eth0 (به جز lo)
        self.assertEqual((rx, tx), (6000, 3500))

    def test_tick_updates_labels_after_first_pass(self):
        monitor, _s, download, upload, total = self._make_monitor(_SAMPLE_PROC)
        contents = iter([_SAMPLE_PROC, _SAMPLE_PROC_T2])
        mocked_open = unittest.mock.mock_open()
        mocked_open.side_effect = lambda *a, **kw: unittest.mock.mock_open(read_data=next(contents))(*a, **kw)
        times = iter([100.0, 101.0])
        with (
            patch("eovpn.network_monitor.open", mocked_open),
            patch("eovpn.network_monitor.time.monotonic", side_effect=lambda: next(times)),
        ):
            self.assertTrue(monitor.tick())  # first pass: baseline only
            self.assertEqual(download.texts, [])
            self.assertTrue(monitor.tick())  # second pass: +1000 RX, +500 TX over 1s
        self.assertEqual(download.texts, ["1000.0 B/s"])
        self.assertEqual(upload.texts, ["500.0 B/s"])
        self.assertEqual(total.texts, ["2.9 KB"])

    def test_stop_removes_source(self):
        monitor, scheduler, _d, _u, _t = self._make_monitor(_SAMPLE_PROC)
        monitor.start()
        self.assertTrue(monitor.running)
        monitor.stop()
        self.assertFalse(monitor.running)
        self.assertEqual(scheduler.removed, ["source-id"])


if __name__ == "__main__":
    unittest.main()
