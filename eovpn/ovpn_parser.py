"""
eOVPN-Pro OpenVPN Configuration Parser Module
ماژول تجزیه فایل‌های پیکربندی OpenVPN در eOVPN-Pro

Parses .ovpn configuration files for remote endpoints, protocol declarations,
and transport characteristics.
تجزیه فایل‌های کانفیگ .ovpn برای استخراج اندپوینت‌ها و پروتکل‌ها.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

PROTO_TCP = "tcp"
PROTO_UDP = "udp"
PROTO_ALL = "all"
DEFAULT_OVPN_PROTO = PROTO_UDP


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
        with open(file_path, encoding="utf-8", errors="ignore") as handle:
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


def parse_ovpn_remote(file_path: str) -> list[tuple[str, int]]:
    """
    Parses an .ovpn file and extracts the list of (host, port) from remote directives.
    پارس کردن فایل .ovpn و استخراج آدرس سرورها و پورت‌های مقصد از خطوط remote.

    :param file_path: Path to the .ovpn configuration file.
    :return: List of (host, port) tuples.
    """
    return [(host, port) for host, port, _proto in parse_ovpn_endpoints(file_path)]
