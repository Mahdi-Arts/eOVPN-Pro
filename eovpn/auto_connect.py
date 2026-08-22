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
import os
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handshake timing budget / بودجه زمانی دست‌دهی OpenVPN
# ---------------------------------------------------------------------------
# A live OpenVPN TLS handshake + PUSH typically completes in 3–8 seconds.
# The floor keeps flaky NAT / DPI paths in the game; the ceiling prevents a
# dead endpoint from stalling the whole cascade.
# دست‌دهی TLS اوپن‌وی‌پی‌ان معمولاً ۳ تا ۸ ثانیه طول می‌کشد. کف زمانی برای
# مسیرهای ناپایدار و سقف زمانی برای جلوگیری از گیر کردن روی سرور مرده است.
BASE_HANDSHAKE_SECONDS = 10.0
UNKNOWN_RTT_TIMEOUT_SECONDS = 12.0
MIN_ATTEMPT_TIMEOUT_SECONDS = 8.0
MAX_ATTEMPT_TIMEOUT_SECONDS = 20.0
RTT_TIMEOUT_MULTIPLIER = 8.0
DISCONNECT_SETTLE_SECONDS = 0.55
PROGRESS_TICK_MS = 100
MAX_CASCADE_CANDIDATES = 50

PROTO_TCP = "tcp"
PROTO_UDP = "udp"
PROTO_ALL = "all"

# OpenVPN's documented default transport when neither `proto` nor a
# per-remote protocol token is present.
# پیش‌فرض مستند OpenVPN وقتی نه `proto` و نه پروتکل روی remote آمده باشد.
DEFAULT_OVPN_PROTO = PROTO_UDP


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


def normalize_proto(token: str | None) -> str | None:
    """
    Maps an OpenVPN proto token (tcp, tcp4, tcp-client, udp6, …) to tcp/udp.
    نگاشت توکن پروتکل OpenVPN به یکی از دو مقدار tcp یا udp.
    """
    if not token:
        return None
    lowered = str(token).strip().lower()
    if lowered.startswith("tcp"):
        return PROTO_TCP
    if lowered.startswith("udp"):
        return PROTO_UDP
    return None


def parse_ovpn_endpoints(file_path: str) -> list[tuple[str, int, str]]:
    """
    Parses ``remote`` / ``proto`` directives from an .ovpn file.

    Returns a list of ``(host, port, proto)`` tuples. The file-level ``proto``
    (default: UDP) is used unless a remote overrides it with a 3rd/4th token.
    پارس خطوط remote و proto و بازگرداندن فهرست (میزبان، پورت، پروتکل).

    :param file_path: Absolute path to the configuration file.
    :return: Endpoint tuples. Empty when the file cannot be read or has no remotes.
    """
    endpoints: list[tuple[str, int, str]] = []
    file_proto = DEFAULT_OVPN_PROTO
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                parts = line.split()
                if not parts:
                    continue
                key = parts[0].lower()
                if key == "proto" and len(parts) >= 2:
                    parsed = normalize_proto(parts[1])
                    if parsed:
                        file_proto = parsed
                    continue
                if key != "remote" or len(parts) < 2:
                    continue
                host = parts[1]
                port = 1194
                proto = file_proto
                if len(parts) >= 3 and parts[2].isdigit():
                    port = int(parts[2])
                    if len(parts) >= 4:
                        parsed = normalize_proto(parts[3])
                        if parsed:
                            proto = parsed
                elif len(parts) >= 3:
                    parsed = normalize_proto(parts[2])
                    if parsed:
                        proto = parsed
                endpoints.append((host, port, proto))
    except Exception as exc:
        logger.error("Error parsing endpoints from %s: %s", file_path, exc)
    return endpoints


def parse_ovpn_protocols(file_path: str) -> frozenset[str]:
    """
    Returns the set of transports declared by an .ovpn file ({tcp}, {udp}, or both).
    مجموعه پروتکل‌های اعلام‌شده در یک فایل کانفیگ را برمی‌گرداند.
    """
    if not file_path or not os.path.isfile(file_path):
        return frozenset()
    return frozenset(proto for _host, _port, proto in parse_ovpn_endpoints(file_path))


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

    queue: list[str] = []
    for name in files:
        if (
            skip_unreachable
            and has_any_rtt
            and name in latencies
            and latencies[name] is None
        ):
            continue
        queue.append(name)
        if len(queue) >= limit:
            break

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
