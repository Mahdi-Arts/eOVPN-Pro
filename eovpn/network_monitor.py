"""
eOVPN-Pro Live Bandwidth Monitor
مانیتور زنده پهنای باند eOVPN-Pro

Reads kernel network counters from ``/proc/net/dev`` once per tick (single
pass) and updates three label callbacks with download speed, upload speed and
total traffic. Extracted from ``MainWindow`` so it is testable without GTK;
only the label callbacks know about widgets.

شمارنده‌های شبکه هسته را از ``/proc/net/dev`` در هر تیک فقط یک‌بار می‌خواند و سه
callback برچسب را با سرعت دانلود، سرعت آپلود و حجم کل به‌روزرسانی می‌کند. از
``MainWindow`` استخراج شده تا بدون GTK قابل تست باشد؛ فقط callbackهای برچسب
با ویجت‌ها سروکار دارند.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from typing import Any

from .timers import TimerScheduler
from .utils import format_data_size, format_throughput

logger = logging.getLogger(__name__)

# Interfaces that identify VPN tunnels in /proc/net/dev.
# اینترفیس‌هایی که تونل VPN را در /proc/net/dev مشخص می‌کنند.
_VPN_IFACE_MARKERS = ("tun", "tap", "ovpn", "ppp", "wg")

LabelCallback = Callable[[str], None]


class NetworkMonitor:
    """
    Polls ``/proc/net/dev`` and reports live throughput to label callbacks.

    A present-but-idle VPN interface reports real zeroes; the fallback to all
    non-loopback interfaces only kicks in when no VPN interface exists at all.

    ``/proc/net/dev`` را می‌خواند و نرخ لحظه‌ای را به callbackهای برچسب می‌دهد.
    اینترفیس VPN موجود ولی بی‌ترافیک صفر واقعی نشان می‌دهد؛ بازگشت به همه
    اینترفیس‌های غیر loopback فقط وقتی رخ می‌دهد که اصلاً اینترفیس VPN نباشد.
    """

    def __init__(
        self,
        scheduler: TimerScheduler,
        download_label: LabelCallback,
        upload_label: LabelCallback,
        total_label: LabelCallback,
    ) -> None:
        self._scheduler = scheduler
        self._download_label = download_label
        self._upload_label = upload_label
        self._total_label = total_label
        self._source_id: Any = None
        self._last_rx = 0
        self._last_tx = 0
        self._last_time: float | None = None

    @property
    def running(self) -> bool:
        """True while the periodic poll is scheduled."""
        return self._source_id is not None

    def start(self) -> None:
        """Starts the 1-second polling loop (idempotent)."""
        self.stop()
        self._last_rx = 0
        self._last_tx = 0
        self._last_time = None
        self._source_id = self._scheduler.add_timeout_seconds(1, self.tick)

    def stop(self) -> None:
        """Stops the polling loop, if running."""
        if self._source_id is not None:
            self._scheduler.remove_timeout(self._source_id)
            self._source_id = None

    def tick(self) -> bool:
        """
        Reads the counters once, updates labels and re-arms itself.

        یک‌بار شمارنده‌ها را می‌خواند، برچسب‌ها را به‌روز می‌کند و دوباره خود را
        زمان‌بندی می‌کند.
        """
        try:
            rx, tx, _vpn_found = self._read_counters()
            now = time.monotonic()

            if self._last_time is not None:
                dt = now - self._last_time
                if dt <= 0:
                    dt = 1.0
                if self._last_rx > 0 or self._last_tx > 0:
                    dl_speed = max(0.0, (rx - self._last_rx) / dt)
                    ul_speed = max(0.0, (tx - self._last_tx) / dt)
                    self._download_label(format_throughput(dl_speed))
                    self._upload_label(format_throughput(ul_speed))
                self._total_label(format_data_size(rx + tx))

            self._last_rx = rx
            self._last_tx = tx
            self._last_time = now
        except Exception as exc:  # pragma: no cover - defensive against /proc quirks
            logger.error("Error in network monitor: %s", exc)
        return True

    def _read_counters(self) -> tuple[int, int, bool]:
        """
        Single-pass read of ``/proc/net/dev``.

        Returns ``(vpn_rx, vpn_tx, vpn_found)``; when no VPN interface exists
        the totals of all non-loopback interfaces are returned instead.

        خواندن تک‌گذره ``/proc/net/dev``؛ وقتی هیچ اینترفیس VPN وجود نداشته باشد،
        جمع همه اینترفیس‌های غیر loopback بازگردانده می‌شود.
        """
        vpn_rx = vpn_tx = 0
        fallback_rx = fallback_tx = 0
        vpn_found = False

        if not os.path.exists("/proc/net/dev"):
            return 0, 0, False

        with open("/proc/net/dev", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if ":" not in line:
                    continue
                iface, stats = line.split(":", 1)
                iface = iface.strip()
                values = stats.split()
                if len(values) < 9:
                    continue
                try:
                    rx = int(values[0])
                    tx = int(values[8])
                except ValueError:
                    continue

                if any(marker in iface for marker in _VPN_IFACE_MARKERS):
                    vpn_found = True
                    vpn_rx += rx
                    vpn_tx += tx
                elif "lo" not in iface:
                    fallback_rx += rx
                    fallback_tx += tx

        if not vpn_found:
            return fallback_rx, fallback_tx, False
        return vpn_rx, vpn_tx, True
