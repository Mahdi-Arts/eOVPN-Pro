"""
eOVPN-Pro Cascading Auto-Connect Engine
موتور اتصال آبشاری به سرورهای لیست‌شده در eOVPN-Pro

Builds an ordered candidate queue from the currently visible (sorted + filtered)
server list and computes a professional per-attempt handshake timeout. The GTK
layer drives connect/disconnect; this module stays UI-free and unit-testable.
این ماژول صف کاندیدا را از لیستِ مرتب و فیلترشده می‌سازد و بودجه زمانی
حرفه‌ای هر تلاش را محاسبه می‌کند. لایه GTK مسئول فراخوانی اتصال/قطع است.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from .ovpn_parser import (
    DEFAULT_OVPN_PROTO,
    PROTO_ALL,
    PROTO_TCP,
    PROTO_UDP,
    normalize_proto,
    parse_ovpn_endpoints,
    parse_ovpn_protocols,
)

logger = logging.getLogger(__name__)

# Public API surface. Symbols imported from ``ovpn_parser`` are deliberately
# re-exported here so that downstream modules (``main_window``, ``eovpn_base``,
# ``cascade_controller`` and the test suite) can import them from a single
# facade instead of reaching into the parser directly.
#
# سطح API عمومی. نمادهای ایمپورت‌شده از ovpn_parser عمداً از اینجا بازصادر
# می‌شوند تا ماژول‌های پایین‌دست بتوانند از یک نمای واحد ایمپورت کنند.
__all__ = [
    # Re-exported from ovpn_parser / بازصادر از ovpn_parser
    "DEFAULT_OVPN_PROTO",
    "PROTO_ALL",
    "PROTO_TCP",
    "PROTO_UDP",
    "normalize_proto",
    "parse_ovpn_endpoints",
    "parse_ovpn_protocols",
    # Timing constants / ثابت‌های زمانی
    "BASE_HANDSHAKE_SECONDS",
    "UNKNOWN_RTT_TIMEOUT_SECONDS",
    "MIN_ATTEMPT_TIMEOUT_SECONDS",
    "MAX_ATTEMPT_TIMEOUT_SECONDS",
    "RTT_TIMEOUT_MULTIPLIER",
    "DISCONNECT_SETTLE_SECONDS",
    "PROGRESS_TICK_MS",
    "MAX_CASCADE_CANDIDATES",
    # Types / نوع‌ها
    "CascadePhase",
    "CascadeAttempt",
    # Functions / توابع
    "compute_attempt_timeout",
    "collect_visible_filenames",
    "build_cascade_queue",
    "format_proto_badge",
    "proto_badge_css",
]

# ---------------------------------------------------------------------------
# Handshake timing budget / بودجه زمانی دست‌دهی OpenVPN
# ---------------------------------------------------------------------------
# Auto-connect gives every real handshake a bounded 30-second opportunity.
# The upper bound still prevents a dead endpoint from stalling the whole
# cascade indefinitely, while measured RTT can add a bounded grace period.
# اتصال آبشاری عمداً برای هر handshake واقعی حداقل یک دقیقه فرصت می‌دهد؛
# سقف زمانی از گیرکردن دائمی روی مقصد مرده جلوگیری می‌کند.
BASE_HANDSHAKE_SECONDS = 30.0
UNKNOWN_RTT_TIMEOUT_SECONDS = 30.0
MIN_ATTEMPT_TIMEOUT_SECONDS = 30.0
MAX_ATTEMPT_TIMEOUT_SECONDS = 45.0
RTT_TIMEOUT_MULTIPLIER = 8.0
DISCONNECT_SETTLE_SECONDS = 0.55
PROGRESS_TICK_MS = 100
MAX_CASCADE_CANDIDATES = 50


class CascadePhase(str, Enum):
    """Lifecycle of a cascade run / چرخه حیات یک اجرای آبشاری."""

    IDLE = "idle"
    PREPARING = "preparing"
    CONNECTING = "connecting"
    SETTLING = "settling"
    SUCCEEDED = "succeeded"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"


@dataclass
class CascadeAttempt:
    """Snapshot of a single handshake attempt / نمای یک تلاش اتصال."""

    filename: str
    index: int
    total: int
    timeout: float
    rtt_ms: float | None = None
    protocols: frozenset[str] = field(default_factory=frozenset)
    reason: str | None = None


def compute_attempt_timeout(rtt_ms: float | None) -> float:
    """
    Adaptive handshake timeout derived from the measured TCP RTT.

    ``timeout = clamp(BASE + (rtt_s * multiplier), MIN, MAX)``

    Unknown / invalid RTT falls back to ``UNKNOWN_RTT_TIMEOUT_SECONDS``.
    تایم‌اوت تطبیقی دست‌دهی بر اساس پینگ اندازه‌گیری‌شده.

    :param rtt_ms: Round-trip time in milliseconds, or ``None`` if unknown.
    :return: Timeout in seconds, rounded to two decimals.
    """
    if rtt_ms is None:
        return UNKNOWN_RTT_TIMEOUT_SECONDS
    try:
        rtt = float(rtt_ms)
    except (TypeError, ValueError):
        return UNKNOWN_RTT_TIMEOUT_SECONDS
    if rtt < 0:
        return UNKNOWN_RTT_TIMEOUT_SECONDS
    budget = BASE_HANDSHAKE_SECONDS + (rtt / 1000.0) * RTT_TIMEOUT_MULTIPLIER
    clamped = min(MAX_ATTEMPT_TIMEOUT_SECONDS, max(MIN_ATTEMPT_TIMEOUT_SECONDS, budget))
    return round(clamped, 2)


def collect_visible_filenames(list_box) -> list[str]:
    """
    Walks a Gtk.ListBox in visual order (already sorted + filtered by GTK).
    پیمایش ListBox به ترتیب نمایش (مرتب و فیلترشده توسط GTK).
    """
    if list_box is None:
        return []
    files: list[str] = []
    index = 0
    while True:
        try:
            row = list_box.get_row_at_index(index)
        except Exception:
            break
        if row is None:
            break
        name = getattr(row, "filename", None)
        if name:
            files.append(str(name))
        index += 1
    return files


def build_cascade_queue(
    visible_files: list[str] | None,
    latencies: dict[str, float | None] | None = None,
    *,
    skip_unreachable: bool = True,
    max_candidates: int = MAX_CASCADE_CANDIDATES,
) -> list[str]:
    """
    Builds the connect-attempt queue from the caller's visible list.

    Visual order is preserved (fastest-first if the user enabled Sort).
    Servers that already failed the speed test (``latencies[name] is None``)
    are skipped when at least one reachable measurement exists, so the
    cascade does not burn a full handshake budget on known-dead endpoints.
    If that filter would empty the queue, the original visible order is used.
    ساخت صف تلاش اتصال با حفظ ترتیب نمایش کاربر.

    :param visible_files: Filenames in the current ListBox order.
    :param latencies: Mapping filename → RTT ms (``None`` = unreachable).
    :param skip_unreachable: Drop speed-test failures when any RTT exists.
    :param max_candidates: Hard cap so a huge list cannot run for hours.
    :return: Ordered filenames to try.
    """
    files = [name for name in (visible_files or []) if name]
    if not files:
        return []

    limit = max(1, int(max_candidates))
    latencies = latencies or {}
    has_any_rtt = any(value is not None for value in latencies.values())

    eligible = []
    for position, name in enumerate(files):
        if skip_unreachable and has_any_rtt and name in latencies and latencies[name] is None:
            continue
        eligible.append((position, name))

    if has_any_rtt:
        # Auto-connect must choose by measured latency even when the user has
        # disabled visual sorting or changed a presentation-only filter.
        def latency_key(item: tuple[int, str]) -> tuple[bool, float, int]:
            value = latencies.get(item[1])
            return (value is None, float("inf") if value is None else value, item[0])

        eligible.sort(key=latency_key)

    queue = [name for _position, name in eligible[:limit]]

    if not queue:
        return files[:limit]
    return queue


def format_proto_badge(protocols: set[str] | frozenset[str] | None) -> str:
    """
    Compact badge text for a configuration's transports (TCP / UDP / TCP/UDP).
    متن فشرده نشان پروتکل برای ردیف لیست.
    """
    protos = set(protocols or ())
    has_tcp = PROTO_TCP in protos
    has_udp = PROTO_UDP in protos
    if has_tcp and has_udp:
        return "TCP/UDP"
    if has_tcp:
        return "TCP"
    if has_udp:
        return "UDP"
    return ""


def proto_badge_css(protocols: set[str] | frozenset[str] | None) -> str:
    """CSS modifier class for the protocol badge / کلاس CSS نشان پروتکل."""
    protos = set(protocols or ())
    has_tcp = PROTO_TCP in protos
    has_udp = PROTO_UDP in protos
    if has_tcp and has_udp:
        return "proto-both"
    if has_tcp:
        return "proto-tcp"
    if has_udp:
        return "proto-udp"
    return ""
