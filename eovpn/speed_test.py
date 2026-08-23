"""
eOVPN-Pro High-Performance Speed & Latency Test Module
ماژول پرسرعت و موازی سنجش تأخیر و پینگ سرورها در eOVPN-Pro

Measures socket-level round-trip time (TCP latency) to remote OpenVPN endpoints concurrently.
محاسبه همزمان و چندنخی میزان تأخیر دست‌دهی شبکه (TCP RTT) به سرورهای OpenVPN.
"""

from __future__ import annotations

import logging
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .ovpn_parser import parse_ovpn_remote

logger = logging.getLogger(__name__)

# Conservative caps prevent a huge or maliciously crafted config list from
# opening too many parallel sockets or running indefinitely.
# محدودیت‌های محافظه‌کارانه جلوی سوکت‌های همزمان بیش از حد را می‌گیرند.
MAX_WORKERS = 16
MAX_ENDPOINTS_PER_CONFIG = 16


def ping_host(host: str, port: int, timeout: float = 1.5) -> float | None:
    """
    Measures TCP connection latency to a host and port.
    If the connection succeeds or is refused (host replied with RST, meaning alive), returns RTT in ms.
    محاسبه تأخیر رفت‌وبرگشت (RTT) بر حسب میلی‌ثانیه از طریق سوکت TCP.

    :param host: Target hostname or IP address.
    :param port: Target port number.
    :param timeout: Socket timeout in seconds.
    :return: Latency in milliseconds or None if unreachable.
    """
    t0 = time.perf_counter()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        rtt = (time.perf_counter() - t0) * 1000.0
        s.close()
        return round(rtt, 1)
    except ConnectionRefusedError:
        # Host is reachable and actively rejected the connection
        # سرور فعال بوده و پکت بازنشانی ارتباط (RST) ارسال کرده است
        rtt = (time.perf_counter() - t0) * 1000.0
        return round(rtt, 1)
    except Exception:
        return None


def test_single_ovpn(file_path: str, timeout: float = 1.5) -> float | None:
    """
    Tests latency for a single .ovpn file by querying its remote endpoints.
    Returns the lowest RTT found among all declared endpoints.
    تست سرعت برای یک کانفیگ منفرد و بازگرداندن کمترین پینگ ثبت‌شده.
    """
    remotes = parse_ovpn_remote(file_path)
    if not remotes:
        return None

    best_rtt = None
    for host, port in remotes[:MAX_ENDPOINTS_PER_CONFIG]:
        # Skip malformed endpoint declarations without scanning private
        # networks beyond what the user-provided config explicitly contains.
        if not host or not (1 <= int(port) <= 65535):
            continue
        rtt = ping_host(host, port, timeout=timeout)
        if rtt is not None and (best_rtt is None or rtt < best_rtt):
            best_rtt = rtt
    return best_rtt


def test_all_configs(
    config_dir: str, file_list: list[str], timeout: float = 1.5, max_workers: int = 12
) -> dict[str, float | None]:
    """
    Runs latency tests on a list of .ovpn files concurrently using a thread pool.
    اجرای موازی و ناهمگام تست پینگ بر روی لیست کانفیگ‌ها با استفاده از استخر نخ‌ها.

    :param config_dir: Directory where .ovpn files reside.
    :param file_list: List of configuration filenames.
    :param timeout: Per-endpoint timeout in seconds.
    :param max_workers: Number of parallel worker threads.
    :return: Dictionary mapping filename -> RTT in milliseconds.
    """
    results: dict[str, float | None] = {}
    valid_files = [f for f in file_list if f and f.endswith(".ovpn")]
    if not valid_files:
        return results

    max_workers = max(1, min(int(max_workers), MAX_WORKERS))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {}
        for file in valid_files:
            full_path = os.path.join(config_dir, file)
            future = executor.submit(test_single_ovpn, full_path, timeout)
            future_to_file[future] = file

        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                rtt = future.result()
                results[file] = rtt
            except Exception as e:
                logger.error("Error testing %s: %s", file, e)
                results[file] = None

    return results
