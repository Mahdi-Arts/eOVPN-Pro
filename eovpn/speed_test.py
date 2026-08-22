"""
Concurrent TCP latency measurement for OpenVPN configurations.
اندازه‌گیری هم‌زمان تأخیر TCP برای کانفیگ‌های OpenVPN.

UDP endpoints are deliberately reported as unmeasured rather than probed with
TCP and incorrectly labelled offline. ``math.inf`` means a TCP endpoint was
actually attempted and unreachable; ``None`` means no TCP measurement exists.
سرورهای UDP عمداً با TCP آزمایش نمی‌شوند تا به‌اشتباه آفلاین گزارش نشوند.
``math.inf`` یعنی TCP واقعاً آزمایش و ناموفق بوده و ``None`` یعنی سنجشی وجود ندارد.
"""

from __future__ import annotations

import logging
import math
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .auto_connect import PROTO_TCP, parse_ovpn_endpoints

logger = logging.getLogger(__name__)


def parse_ovpn_remote(file_path: str) -> list[tuple[str, int]]:
    """Compatibility view of parsed remotes / نمای سازگار از مقصدهای پارس‌شده."""
    return [(host, port) for host, port, _protocol in parse_ovpn_endpoints(file_path)]


def ping_host(host: str, port: int, timeout: float = 1.5) -> float | None:
    """
    Measures one TCP handshake; a refused connection still proves reachability.
    اندازه‌گیری دست‌دهی TCP؛ پاسخ Refused نیز دسترس‌پذیری میزبان را ثابت می‌کند.
    """
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return round((time.perf_counter() - started) * 1000.0, 1)
    except ConnectionRefusedError:
        return round((time.perf_counter() - started) * 1000.0, 1)
    except (OSError, TimeoutError):
        return None


def test_single_ovpn(file_path: str, timeout: float = 1.5) -> float | None:
    """
    Returns best TCP RTT, infinity for attempted failure, or None for UDP-only.
    بازگرداندن بهترین RTT، بی‌نهایت برای شکست واقعی یا None برای کانفیگ فقط UDP.
    """
    tcp_endpoints = [
        (host, port)
        for host, port, protocol in parse_ovpn_endpoints(file_path)
        if protocol == PROTO_TCP
    ]
    if not tcp_endpoints:
        return None

    results = [ping_host(host, port, timeout=timeout) for host, port in tcp_endpoints]
    reachable = [value for value in results if value is not None]
    return min(reachable) if reachable else math.inf


def test_all_configs(
    config_dir: str,
    file_list: list[str] | tuple[str, ...] | None,
    timeout: float = 1.5,
    max_workers: int = 12,
) -> dict[str, float | None]:
    """
    Measures safe filenames concurrently with a bounded worker pool.
    سنجش هم‌زمان نام‌فایل‌های امن با تعداد محدود Worker.
    """
    root = Path(config_dir).resolve()
    valid_files = [
        name
        for name in (file_list or [])
        if name
        and Path(name).name == name
        and Path(name).suffix.lower() == ".ovpn"
        and (root / name).is_file()
        and not (root / name).is_symlink()
    ]
    if not valid_files:
        return {}

    results: dict[str, float | None] = {}
    workers = min(32, max(1, int(max_workers)), len(valid_files))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="eovpn-rtt") as executor:
        futures = {
            executor.submit(test_single_ovpn, str(root / name), timeout): name
            for name in valid_files
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                logger.error("Latency test failed for %s: %s", name, exc)
                results[name] = math.inf
    return results
