"""
Small, UI-independent utility functions used by eOVPN-Pro.
توابع کمکی کوچک و مستقل از رابط کاربری در eOVPN-Pro.

Security-sensitive archive handling lives in :mod:`eovpn.config_import`; this
module keeps only list predicates, OpenVPN directive checks, and a compatibility
wrapper for older callers.
پردازش امنیتی آرشیوها در ماژول :mod:`eovpn.config_import` قرار دارد؛ این ماژول
فقط منطق فیلتر، بررسی دستورات OpenVPN و لایه سازگاری فراخوان‌های قدیمی را نگه
می‌دارد.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path

from .config_import import (
    MAX_ARCHIVE_BYTES,
    MAX_EXTRACTED_BYTES,
    ConfigurationImportError,
    import_configurations,
)

logger = logging.getLogger(__name__)

# Backward-compatible names for downstream users / نام‌های سازگار با نسخه‌های قبلی.
MAX_ZIP_DOWNLOAD_BYTES = MAX_ARCHIVE_BYTES
MAX_EXTRACTED_TOTAL_BYTES = MAX_EXTRACTED_BYTES


class NotZipException(ConfigurationImportError):
    """Compatibility error for invalid import sources / خطای سازگاری منبع نامعتبر."""


def is_safe_path(base_dir: str, path: str, follow_symlinks: bool = True) -> bool:
    """
    Returns whether ``path`` resolves inside ``base_dir``.
    بررسی می‌کند مسیر نهایی درون پوشه پایه باقی می‌ماند یا خیر.
    """
    base = os.path.realpath(base_dir)
    candidate = os.path.realpath(path) if follow_symlinks else os.path.abspath(path)
    try:
        return os.path.commonpath((base, candidate)) == base
    except ValueError:
        return False


def latency_state(value: float | None, measured: bool = True) -> str:
    """
    Maps a latency value to ``online``, ``offline``, or ``unknown``.
    نگاشت مقدار تأخیر به وضعیت آنلاین، آفلاین یا نامشخص.
    """
    if not measured or value is None:
        return "unknown"
    try:
        return "online" if math.isfinite(float(value)) else "offline"
    except (TypeError, ValueError):
        return "unknown"


def matches_server_filter(
    name: str,
    *,
    search: str = "",
    mode: str = "all",
    favorites: set[str] | None = None,
    latencies: dict[str, float | None] | None = None,
    proto_mode: str = "all",
    protocols: set[str] | frozenset[str] | None = None,
) -> bool:
    """
    Pure search, status, favorite, and protocol predicate.
    گزاره خالص جست‌وجو، وضعیت، علاقه‌مندی و پروتکل سرورها.
    """
    name = name or ""
    if search and search.casefold() not in name.casefold():
        return False

    if mode == "favorites" and name not in (favorites or set()):
        return False

    measured = latencies is not None and name in latencies
    state = latency_state((latencies or {}).get(name), measured)
    if mode == "online" and state != "online":
        return False
    if mode == "offline" and state != "offline":
        return False

    if proto_mode in ("tcp", "udp") and proto_mode not in (protocols or set()):
        return False
    return True


def download_remote_to_destination(remote: str, destination: str) -> list[str]:
    """
    Compatibility wrapper returning imported certificate names.
    لایه سازگاری که نام گواهی‌های واردشده را بازمی‌گرداند.
    """
    try:
        return list(import_configurations(remote, destination).certificates)
    except ConfigurationImportError as exc:
        raise NotZipException(str(exc)) from exc


def ovpn_is_auth_required(ovpn_file: str) -> bool:
    """
    Detects an active ``auth-user-pass`` directive, excluding comments.
    تشخیص دستور فعال ``auth-user-pass`` با نادیده‌گرفتن توضیحات.
    """
    try:
        with Path(ovpn_file).open("r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith(("#", ";")):
                    continue
                directive = line.split(maxsplit=1)[0].lower()
                if directive == "auth-user-pass":
                    return True
    except OSError as exc:
        logger.error("Could not inspect OpenVPN authentication directive in %s: %s", ovpn_file, exc)
    return False
