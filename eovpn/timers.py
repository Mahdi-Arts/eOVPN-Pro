"""
eOVPN-Pro Timer Scheduler Abstraction
انتزاع زمان‌بند رویدادها در eOVPN-Pro

Provides an injectable timer interface so state machines (cascade controller,
network monitor) stay free of a hard GLib dependency at import time. The GLib
implementation imports PyGObject lazily, which keeps every consumer of this
module unit-testable in an environment without GTK.

یک رابط زمان‌بند قابل تزریق فراهم می‌کند تا ماشین‌های حالت (کنترلر آبشار،
مانیتور شبکه) در زمان ایمپورت وابستگی سخت به GLib نداشته باشند. پیاده‌سازی GLib
به‌صورت تنبل PyGObject را ایمپورت می‌کند و به همین دلیل مصرف‌کنندگان این ماژول
در محیط بدون GTK نیز قابل تست واحد هستند.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

# A timeout callback returns True to keep firing, False to stop.
# callback تایم‌اوت برای ادامه اجرا True و برای توقف False برمی‌گرداند.
TimeoutCallback = Callable[[], bool]


class TimerScheduler(Protocol):
    """Minimal timer interface used by the pure controllers."""

    def add_timeout(self, interval_ms: int, callback: TimeoutCallback) -> Any:
        """Schedules ``callback`` after ``interval_ms`` milliseconds."""
        ...

    def add_timeout_seconds(self, interval_seconds: int, callback: TimeoutCallback) -> Any:
        """Schedules ``callback`` after ``interval_seconds`` seconds."""
        ...

    def remove_timeout(self, source_id: Any) -> None:
        """Cancels a previously scheduled timeout."""
        ...


class GLibTimerScheduler:
    """
    GLib-backed timer scheduler.

    GLib is imported lazily so importing this module never requires PyGObject.

    زمان‌بند مبتنی بر GLib؛ ایمپورت GLib تنبل است تا ایمپورت این ماژول هرگز
    به PyGObject نیاز نداشته باشد.
    """

    def __init__(self) -> None:
        # Lazy import keeps the module importable without PyGObject.
        # ایمپورت تنبل ماژول را بدون PyGObject قابل ایمپورت نگه می‌دارد.
        from gi.repository import GLib

        self._glib = GLib

    def add_timeout(self, interval_ms: int, callback: TimeoutCallback) -> Any:
        return self._glib.timeout_add(interval_ms, callback)

    def add_timeout_seconds(self, interval_seconds: int, callback: TimeoutCallback) -> Any:
        return self._glib.timeout_add_seconds(interval_seconds, callback)

    def remove_timeout(self, source_id: Any) -> None:
        self._glib.source_remove(source_id)


def create_default_scheduler() -> TimerScheduler:
    """
    Returns the platform scheduler used by the real application.

    بازگرداندن زمان‌بند پلتفرم که برنامه واقعی از آن استفاده می‌کند.
    """
    return GLibTimerScheduler()
