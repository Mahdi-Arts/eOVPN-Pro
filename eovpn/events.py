"""
eOVPN-Pro Typed Connection Events
رویدادهای تایپ‌شده اتصال در eOVPN-Pro

Normalizes the legacy backend callback payloads (``bool``, ``list`` or an
error argument) into a single typed :class:`ConnectionEvent`. Backends keep
emitting the legacy shapes (no breaking change); consumers receive one
consistent model instead of branching on ``type(result)``.

payloadهای قدیمی callback بک‌اندها (``bool``، ``list`` یا آرگومان خطا) را به یک
مدل تایپ‌شده واحد تبدیل می‌کند. بک‌اندها همچنان شکل قدیمی را ارسال می‌کنند
(بدون تغییر سازش‌ناپذیر)؛ اما مصرف‌کننده به‌جای شاخه‌بندی روی
``type(result)`` یک مدل یکنواخت دریافت می‌کند.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConnectionEventKind(str, Enum):
    """Kinds of connection lifecycle events / انواع رویدادهای چرخه اتصال."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    PROGRESS = "progress"
    PAUSED = "paused"
    RESUMED = "resumed"


@dataclass(frozen=True)
class ConnectionEvent:
    """
    Immutable snapshot of a backend connection event.

    نمای تغییرناپذیر یک رویداد اتصال از بک‌اند.
    """

    kind: ConnectionEventKind
    error: str | None = None
    detail: int | None = None


def normalize_connection_event(result: Any, error: Any = None) -> ConnectionEvent:
    """
    Maps legacy callback payloads to a typed :class:`ConnectionEvent`.

    - ``error`` set          → ``FAILED``
    - ``result is True``     → ``CONNECTED``
    - ``result is False``    → ``DISCONNECTED``
    - ``["pause"]``          → ``PAUSED``
    - ``["resume"]``         → ``RESUMED``
    - other lists            → ``PROGRESS`` (first element kept as ``detail``)

    نگاشت payloadهای قدیمی callback به :class:`ConnectionEvent` تایپ‌شده.
    """
    if error is not None:
        return ConnectionEvent(ConnectionEventKind.FAILED, error=str(error))
    if isinstance(result, bool):
        if result:
            return ConnectionEvent(ConnectionEventKind.CONNECTED)
        return ConnectionEvent(ConnectionEventKind.DISCONNECTED)
    if isinstance(result, (list, tuple)):
        if len(result) == 1 and isinstance(result[-1], str):
            status = result[-1].lower()
            if status == "pause":
                return ConnectionEvent(ConnectionEventKind.PAUSED)
            if status == "resume":
                return ConnectionEvent(ConnectionEventKind.RESUMED)
        detail = None
        if result and isinstance(result[0], int):
            detail = int(result[0])
        return ConnectionEvent(ConnectionEventKind.PROGRESS, detail=detail)
    if result is None:
        return ConnectionEvent(ConnectionEventKind.DISCONNECTED)
    # Unknown shapes degrade to progress rather than crashing the UI.
    # شکل‌های ناشناخته به‌جای از کار انداختن UI به «پیشرفت» تنزل می‌یابند.
    return ConnectionEvent(ConnectionEventKind.PROGRESS)
