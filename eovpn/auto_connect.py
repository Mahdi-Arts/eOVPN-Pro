"""
UI-independent cascade queue, protocol parser, and timeout policy.
صف اتصال آبشاری، پارسر پروتکل و سیاست تایم‌اوت مستقل از رابط کاربری.
"""

from __future__ import annotations

import logging
import math
import shlex
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

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
DEFAULT_OVPN_PROTO = PROTO_UDP


class CascadePhase(str, Enum):
    """Lifecycle of a cascade run / چرخه عمر اجرای اتصال آبشاری."""

    IDLE = "idle"
    PREPARING = "preparing"
    CONNECTING = "connecting"
    SETTLING = "settling"
    SUCCEEDED = "succeeded"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"


def normalize_proto(token: str | None) -> str | None:
    """Normalizes OpenVPN transport variants / یکسان‌سازی انواع پروتکل OpenVPN."""
    lowered = str(token or "").strip().lower()
    if lowered.startswith("tcp"):
        return PROTO_TCP
    if lowered.startswith("udp"):
        return PROTO_UDP
    return None


def _active_directives(file_path: str) -> list[list[str]]:
    """Parses uncommented directives with shell-like quoting / پارس دستورات فعال با پشتیبانی کوتیشن."""
    directives: list[list[str]] = []
    try:
        with Path(file_path).open("r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith(("#", ";")):
                    continue
                try:
                    parts = shlex.split(line, comments=False, posix=True)
                except ValueError:
                    logger.warning("Ignored malformed OpenVPN directive in %s", file_path)
                    continue
                if parts:
                    directives.append(parts)
    except OSError as exc:
        logger.error("Could not parse OpenVPN endpoints from %s: %s", file_path, exc)
    return directives


def parse_ovpn_endpoints(file_path: str) -> list[tuple[str, int, str]]:
    """
    Returns validated ``(host, port, protocol)`` tuples from active directives.
    بازگرداندن سه‌تایی معتبر میزبان، پورت و پروتکل از دستورات فعال.
    """
    directives = _active_directives(file_path)
    file_protocol = DEFAULT_OVPN_PROTO
    for parts in directives:
        if parts[0].lower() == "proto" and len(parts) >= 2:
            file_protocol = normalize_proto(parts[1]) or file_protocol

    endpoints: list[tuple[str, int, str]] = []
    for parts in directives:
        if parts[0].lower() != "remote" or len(parts) < 2:
            continue
        host = parts[1].strip()
        if not host or any(character.isspace() for character in host):
            continue
        port = 1194
        protocol = file_protocol
        if len(parts) >= 3:
            if parts[2].isdigit():
                candidate_port = int(parts[2])
                if not 1 <= candidate_port <= 65535:
                    continue
                port = candidate_port
                if len(parts) >= 4:
                    protocol = normalize_proto(parts[3]) or protocol
            else:
                protocol = normalize_proto(parts[2]) or protocol
        endpoints.append((host, port, protocol))
    return endpoints


def parse_ovpn_protocols(file_path: str) -> frozenset[str]:
    """Returns transports declared by one config / بازگرداندن پروتکل‌های یک کانفیگ."""
    candidate = Path(file_path)
    if not candidate.is_file() or candidate.is_symlink():
        return frozenset()
    return frozenset(protocol for _host, _port, protocol in parse_ovpn_endpoints(file_path))


def compute_attempt_timeout(rtt_ms: float | None) -> float:
    """
    Computes a bounded TLS-handshake budget from a finite TCP RTT.
    محاسبه بودجه محدود دست‌دهی TLS بر اساس RTT معتبر TCP.
    """
    if rtt_ms is None:
        return UNKNOWN_RTT_TIMEOUT_SECONDS
    try:
        rtt = float(rtt_ms)
    except (TypeError, ValueError):
        return UNKNOWN_RTT_TIMEOUT_SECONDS
    if rtt < 0:
        return UNKNOWN_RTT_TIMEOUT_SECONDS
    if not math.isfinite(rtt):
        return MIN_ATTEMPT_TIMEOUT_SECONDS
    budget = BASE_HANDSHAKE_SECONDS + (rtt / 1000.0) * RTT_TIMEOUT_MULTIPLIER
    return round(
        min(MAX_ATTEMPT_TIMEOUT_SECONDS, max(MIN_ATTEMPT_TIMEOUT_SECONDS, budget)),
        2,
    )


def collect_visible_filenames(list_box) -> list[str]:
    """Reads Gtk.ListBox rows in visual order / خواندن ردیف‌ها به ترتیب نمایش."""
    if list_box is None:
        return []
    filenames: list[str] = []
    index = 0
    while True:
        try:
            row = list_box.get_row_at_index(index)
        except Exception as exc:
            logger.debug("Could not read list row %d: %s", index, exc)
            break
        if row is None:
            break
        filename = getattr(row, "filename", None)
        if filename:
            filenames.append(str(filename))
        index += 1
    return filenames


def build_cascade_queue(
    visible_files: list[str] | None,
    latencies: dict[str, float | None] | None = None,
    *,
    skip_unreachable: bool = True,
    max_candidates: int = MAX_CASCADE_CANDIDATES,
) -> list[str]:
    """
    Preserves visible order, skips measured-offline servers, and bounds work.
    حفظ ترتیب نمایشی، رد سرور آفلاینِ سنجیده‌شده و محدودکردن تعداد تلاش‌ها.

    ``None`` is unmeasured (for example UDP-only) and remains eligible;
    ``math.inf`` is an attempted, unreachable TCP endpoint.
    ``None`` به معنی سنجیده‌نشده و ``math.inf`` به معنی TCP آزمایش‌شده و ناموفق است.
    """
    files = [name for name in (visible_files or []) if name]
    if not files:
        return []
    limit = max(1, int(max_candidates))
    measurements = latencies or {}
    has_reachable = any(
        value is not None and math.isfinite(value)
        for value in measurements.values()
    )

    queue: list[str] = []
    for name in files:
        value = measurements.get(name)
        measured_offline = value is not None and not math.isfinite(value)
        if skip_unreachable and has_reachable and measured_offline:
            continue
        queue.append(name)
        if len(queue) >= limit:
            break
    return queue or files[:limit]


def format_proto_badge(protocols: set[str] | frozenset[str] | None) -> str:
    """Returns TCP/UDP badge text / بازگرداندن متن نشان TCP/UDP."""
    values = set(protocols or ())
    if PROTO_TCP in values and PROTO_UDP in values:
        return "TCP/UDP"
    if PROTO_TCP in values:
        return "TCP"
    if PROTO_UDP in values:
        return "UDP"
    return ""


def proto_badge_css(protocols: set[str] | frozenset[str] | None) -> str:
    """Returns the protocol badge CSS modifier / بازگرداندن کلاس CSS نشان پروتکل."""
    values = set(protocols or ())
    if PROTO_TCP in values and PROTO_UDP in values:
        return "proto-both"
    if PROTO_TCP in values:
        return "proto-tcp"
    if PROTO_UDP in values:
        return "proto-udp"
    return ""
