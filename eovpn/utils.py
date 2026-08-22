"""
eOVPN-Pro Utility Functions & Configuration Handlers
توابع کمکی و پردازش فایل‌های پیکربندی در eOVPN-Pro

Provides safe ZIP extraction (Zip-Slip, zip-bomb and duplicate-entry protection),
remote configuration downloads with strict HTTPS validation, certificate
extraction, OpenVPN directive auditing, and the pure server-list search/filter
predicate.

شامل استخراج امن فایل‌های فشرده (محافظت در برابر Zip-Slip، بمب فشرده و ورودی‌های
تکراری)، دانلود امن کانفیگ‌ها با اعتبارسنجی سخت‌گیرانه HTTPS، استخراج گواهی،
ممیزی دایرکتیوهای OpenVPN و تابع خالص جستجو/فیلتر لیست سرورها.
"""

from __future__ import annotations

import contextlib
import gettext
import io
import ipaddress
import logging
import os
import re
import shutil
import urllib.parse
import urllib.request
import zipfile
from typing import Any

from ._meta import app_version

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security limits / محدودیت‌های امنیتی
# ---------------------------------------------------------------------------
MAX_ZIP_DOWNLOAD_BYTES = 64 * 1024 * 1024  # 64 MiB compressed archive cap
MAX_EXTRACTED_TOTAL_BYTES = 256 * 1024 * 1024  # 256 MiB extracted data cap
MAX_FOLDER_IMPORT_TOTAL_BYTES = 256 * 1024 * 1024  # 256 MiB local folder cap
MAX_ZIP_ENTRIES = 20_000

_CHUNK_SIZE = 64 * 1024

# OpenVPN directives that can execute commands, load plugins, or change trust
# boundaries. Imports containing these are surfaced with a security warning.
#
# دایرکتیوهایی که می‌توانند دستور/پلاگین اجرا کنند یا مرز اعتماد را تغییر دهند.
DANGEROUS_OVPN_DIRECTIVES: frozenset[str] = frozenset(
    {
        "up",
        "down",
        "route-up",
        "route-pre-down",
        "route-post-down",
        "ipchange",
        "learn-address",
        "client-connect",
        "client-disconnect",
        "tls-verify",
        "iproute",
        "script-security",
        "setenv",
        "plugin",
        "management",
        "auth-user-pass",
        "auth-user-pass-verify",
        "tls-crypt-v2-verify",
    }
)


class NotZipException(Exception):
    """
    Exception raised when the provided configuration archive is invalid.
    استثنای مربوط به نامعتبر بودن منبع کانفیگ.
    """


class InsecureSourceError(ValueError):
    """
    Raised when a configuration source uses an insecure network scheme.
    زمانی که منبع شبکه از پروتکل امن HTTPS استفاده نکند.
    """


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    HTTP redirect handler that only allows HTTPS destinations.
    ریدایرکت فقط به مقصد HTTPS مجاز است.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme != "https":
            raise InsecureSourceError(gettext.gettext("Insecure redirect blocked: only HTTPS is permitted."))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _read_limited(response: Any) -> bytes:
    """
    Reads a response body while enforcing ``MAX_ZIP_DOWNLOAD_BYTES``.
    خواندن بدنۀ پاسخ با رعایت سقف حجم دانلود.
    """
    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_ZIP_DOWNLOAD_BYTES:
        raise ValueError(gettext.gettext("Configuration archive is too large to download safely."))

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_ZIP_DOWNLOAD_BYTES:
            raise ValueError(gettext.gettext("Configuration archive exceeds the download size limit."))
        chunks.append(chunk)
    return b"".join(chunks)


def is_safe_path(base_dir: str, path: str, follow_symlinks: bool = True) -> bool:
    """
    Verifies that a resolved target path strictly resides within ``base_dir``.

    بررسی امن بودن مسیر هدف و جلوگیری از Path Traversal / Zip Slip.
    """
    base = os.path.realpath(base_dir)
    matchpath = os.path.realpath(path) if follow_symlinks else os.path.abspath(path)
    return os.path.commonpath((base, matchpath)) == base


def is_private_or_loopback_host(host: str | None) -> bool:
    """
    Best-effort check for loopback/private/link-local hosts. DNS is not resolved
    to avoid blocking the UI and to avoid leaking the source URL.

    تشخیص بهترین‌تلاش برای میزبان‌های loopback/private/link-local بدون resolve.
    """
    if not host:
        return False
    if host in {"localhost", "localhost.localdomain"}:
        return True
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        ip = ipaddress.ip_address(host)
        return bool(ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved)
    except ValueError:
        return host.endswith(".local") or host.endswith(".localhost")


def is_hard_blocked_source_host(host: str | None) -> bool:
    """
    Decides whether a configuration source host must be refused outright.

    Localhost, mDNS-style names and literal private/reserved IP addresses are
    blocked (SSRF hardening). Unresolvable hostnames are only *warned* about
    because blocking them would require a DNS lookup, which would block the UI
    and leak the source URL to the resolver.

    تعیین می‌کند آیا میزبان منبع کانفیگ باید قاطعانه رد شود.
    """
    if not host:
        return False
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if host in {"localhost", "localhost.localdomain"}:
        return True
    if host.endswith(".localhost") or host.endswith(".local"):
        return True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return is_private_or_loopback_host(host)


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
    Pure predicate for the server-list search/filter feature.
    تابع خالص منطق جستجو/فیلتر لیست سرورها.
    """
    name = name or ""
    if search and search.lower() not in name.lower():
        return False

    if mode == "favorites" and name not in (favorites or set()):
        return False
    if mode == "online" and (latencies or {}).get(name) is None:
        return False
    if mode == "offline" and (latencies or {}).get(name) is not None:
        return False

    return not (proto_mode in ("tcp", "udp") and proto_mode not in (protocols or set()))


def download_remote_to_destination(remote: str, destination: str) -> list[str]:
    """
    Downloads or copies OpenVPN configuration files into ``destination``.

    Network sources must use HTTPS. Archives are extracted with size limits,
    path-traversal protection, duplicate-name protection and private output
    permissions.

    دانلود/کپی فایل‌های OpenVPN. منابع شبکه حتماً باید HTTPS باشند و استخراج ZIP
    با محدودیت حجم، جلوگیری از عبور مسیر، جلوگیری از ورودی تکراری و مجوزهای امن
    انجام می‌شود.
    """
    ovpn_regex = re.compile(r"\.ovpn$", re.IGNORECASE)
    crt_regex = re.compile(r"(?:\.crt|\.pem|\.ca|cert)(?:$|[\W_])", re.IGNORECASE)

    os.makedirs(destination, exist_ok=True)
    os.chmod(destination, 0o700)
    real_destination = os.path.realpath(destination)

    def make_zip_from_bytes(content: bytes) -> zipfile.ZipFile:
        return zipfile.ZipFile(io.BytesIO(content), "r")

    def fetch_zip_archive(src: str) -> zipfile.ZipFile:
        if os.path.exists(src):
            if os.path.islink(src):
                raise NotZipException(gettext.gettext("Symlink archives are not allowed."))
            if os.path.getsize(src) > MAX_ZIP_DOWNLOAD_BYTES:
                raise ValueError(gettext.gettext("Configuration archive is too large to import safely."))
            with open(src, "rb") as f:
                return make_zip_from_bytes(f.read())

        parsed = urllib.parse.urlparse(src)
        if parsed.scheme and parsed.scheme != "https":
            raise InsecureSourceError(
                gettext.gettext("Insecure configuration source blocked: remote URLs must use HTTPS.")
            )
        if not parsed.scheme:
            raise FileNotFoundError(gettext.gettext("Configuration source was not found."))
        if is_hard_blocked_source_host(parsed.hostname):
            # SSRF guard: localhost and literal private/reserved IPs are refused.
            # نگهبان SSRF: localhost و IPهای خصوصی/رزرو به‌صورت صریح رد می‌شوند.
            raise InsecureSourceError(
                gettext.gettext(
                    "Configuration sources on localhost or private network addresses are blocked."
                )
            )
        if is_private_or_loopback_host(parsed.hostname):
            logger.warning("Config source hostname appears private/loopback: %s", parsed.hostname)

        headers = {
            "User-Agent": (f"eOVPN-Pro/{app_version()} (+https://github.com/Mahdi-Arts/eOVPN-Pro)"),
            "Accept": "application/zip,application/octet-stream,*/*",
            "Connection": "close",
        }
        req = urllib.request.Request(src, headers=headers, method="GET")
        opener = urllib.request.build_opener(_SafeRedirectHandler())
        with opener.open(req, timeout=12.0) as resp:
            return make_zip_from_bytes(_read_limited(resp))

    expanded_remote = os.path.expanduser(remote)

    if os.path.isdir(expanded_remote):
        found_certs: list[str] = []
        try:
            entries = sorted(os.listdir(expanded_remote))
        except Exception as err:
            logger.error("Failed to read directory %s: %s", expanded_remote, err)
            return []

        try:
            total_bytes = 0
            for name in entries:
                src_file = os.path.join(expanded_remote, name)
                if not os.path.isfile(src_file) or os.path.islink(src_file):
                    continue
                if name.endswith((".ovpn", ".crt", ".pem")):
                    total_bytes += os.path.getsize(src_file)
        except Exception as err:
            logger.error("Failed to scan directory %s: %s", expanded_remote, err)
            return []

        if total_bytes > MAX_FOLDER_IMPORT_TOTAL_BYTES:
            raise ValueError(gettext.gettext("Configuration folder is too large to import safely."))

        for file_name in entries:
            src_file = os.path.join(expanded_remote, file_name)
            if os.path.islink(src_file) or not os.path.isfile(src_file):
                continue
            if file_name.endswith((".ovpn", ".crt", ".pem")):
                dest_file = os.path.join(real_destination, file_name)
                if not is_safe_path(real_destination, dest_file):
                    logger.warning("Skipping unsafe file path: %s", file_name)
                    continue
                shutil.copy2(src_file, dest_file)
                with contextlib.suppress(OSError):
                    os.chmod(dest_file, 0o600)
                if file_name.endswith((".crt", ".pem")):
                    found_certs.append(file_name)
        return found_certs

    try:
        zip_file = fetch_zip_archive(expanded_remote)
    except InsecureSourceError:
        raise
    except Exception as exc:
        logger.error("Failed to load ZIP archive from %s: %s", expanded_remote, exc)
        raise NotZipException(
            gettext.gettext("Configuration Source MUST be a valid HTTPS ZIP archive or accessible folder.")
        ) from exc

    with zip_file:
        infos = zip_file.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise NotZipException(gettext.gettext("Configuration archive contains too many entries."))

        configs = [info for info in infos if ovpn_regex.search(info.filename)]
        certs = [info for info in infos if crt_regex.search(info.filename)]
        all_targets = configs + certs

        extracted_certs: list[str] = []
        extracted_total = 0
        seen_names: set[str] = set()
        zip_bomb_detected = False

        for info in all_targets:
            file_name = info.filename
            # Flatten archive paths and refuse repeated basenames, which can
            # otherwise silently overwrite one imported config with another.
            base_name = os.path.basename(file_name)
            if not base_name:
                continue
            if base_name in seen_names:
                logger.warning("Skipping duplicate archive entry name: %s", file_name)
                continue
            seen_names.add(base_name)

            target_path = os.path.join(real_destination, base_name)
            if not is_safe_path(real_destination, target_path):
                logger.warning("Skipping potentially unsafe zip entry: %s", file_name)
                continue

            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(target_path, flags, 0o600)
            except OSError as exc:
                logger.error("Could not open output for %s: %s", file_name, exc)
                continue

            try:
                with os.fdopen(fd, "wb") as dest_stream, zip_file.open(info, "r") as source_stream:
                    while True:
                        chunk = source_stream.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        dest_stream.write(chunk)
                        extracted_total += len(chunk)
                        if extracted_total > MAX_EXTRACTED_TOTAL_BYTES:
                            zip_bomb_detected = True
                            logger.error("Extraction aborted: uncompressed size limit exceeded.")
                            break
                with contextlib.suppress(OSError):
                    os.chmod(target_path, 0o600)

                if zip_bomb_detected:
                    break

                if crt_regex.search(base_name):
                    extracted_certs.append(base_name)
            except Exception as e:
                logger.error("Error extracting %s: %s", file_name, e)
                with contextlib.suppress(OSError):
                    os.remove(target_path)

        if zip_bomb_detected:
            raise NotZipException(
                gettext.gettext("Configuration archive appears to be a zip bomb and was rejected.")
            )

    return extracted_certs


def ovpn_is_auth_required(ovpn_file: str) -> bool:
    """
    Checks whether an .ovpn file specifies ``auth-user-pass``.

    Stops at the first match instead of reading the whole file.
    بررسی وجود دایرکتیو auth-user-pass؛ با اولین تطابق متوقف می‌شود.
    """
    try:
        with open(ovpn_file, encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith(("#", ";")) or not stripped:
                    continue
                if "auth-user-pass" in stripped:
                    return True
        return False
    except Exception as e:
        logger.error("Error reading %s: %s", ovpn_file, e)
        return False


def format_throughput(bytes_per_sec: float) -> str:
    """Formats a transfer rate as B/s, KB/s or MB/s."""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.1f} B/s"
    if bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"


def format_data_size(bytes_total: float) -> str:
    """Formats a cumulative byte count as B, KB, MB or GB."""
    if bytes_total < 1024:
        return f"{bytes_total} B"
    if bytes_total < 1024 * 1024:
        return f"{bytes_total / 1024:.1f} KB"
    if bytes_total < 1024 * 1024 * 1024:
        return f"{bytes_total / (1024 * 1024):.1f} MB"
    return f"{bytes_total / (1024 * 1024 * 1024):.1f} GB"


def audit_ovpn_content(file_path: str) -> list[str]:
    """
    Scans an .ovpn file for executable, plugin or trust-sensitive directives.

    External credential references and executable directives are reported so
    users can review imported profiles before connecting.

    پویش فایل کانفیگ از نظر دایرکتیوهای اجرایی، پلاگین، ارجاع اعتبارنامه یا
    دیگر دایرکتیوهای حساس اعتماد.
    """
    found: set[str] = set()
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                parts = line.split()
                key = parts[0].lower()
                if key not in DANGEROUS_OVPN_DIRECTIVES:
                    continue
                # Plain auth-user-pass is the normal Keyring-backed flow and
                # is not itself executable; only external credential files are
                # reported. / شکل بدون آرگومان امن است؛ فقط فایل خارجی گزارش شود.
                if key == "auth-user-pass" and len(parts) < 2:
                    continue
                found.add(key)
    except Exception as exc:
        logger.error("Error auditing %s: %s", file_path, exc)
    return sorted(found)
