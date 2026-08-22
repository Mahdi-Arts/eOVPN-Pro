"""
eOVPN-Pro Utility Functions & Configuration Handlers
توابع کمکی و پردازش فایل‌های پیکربندی در eOVPN-Pro

Provides safe ZIP extraction (Zip-Slip + zip-bomb protection), remote
configuration downloads with strict URL validation, certificate extraction,
and the pure server-list search/filter predicate.
شامل استخراج امن فایل‌های فشرده (محافظت در برابر Zip-Slip و بمب فشرده)، دانلود
ایمن کانفیگ‌ها با اعتبارسنجی سخت‌گیرانه آدرس، استخراج گواهی‌ها و تابع خالص
جستجو/فیلتر لیست سرورها.
"""

import gettext
import io
import logging
import os
import re
import shutil
import urllib.parse
import urllib.request
import zipfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security limits / محدودیت‌های امنیتی
# ---------------------------------------------------------------------------
MAX_ZIP_DOWNLOAD_BYTES = 64 * 1024 * 1024      # 64 MiB compressed archive cap
MAX_EXTRACTED_TOTAL_BYTES = 256 * 1024 * 1024  # 256 MiB extracted data cap

_CHUNK_SIZE = 64 * 1024


class NotZipException(Exception):
    """
    Exception raised when the provided configuration archive is invalid.
    استثنای مربوط به نامعتبر بودن فایل فشرده کانفیگ.
    """
    pass


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    HTTP redirect handler that only allows http/https destinations.
    جلوگیری از حملات open-redirect به پروتکل‌های غیرمجاز هنگام دنبال‌کردن ریدایرکت.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                gettext.gettext("Unsafe redirect blocked: only HTTP and HTTPS are permitted.")
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _read_limited(response) -> bytes:
    """
    Reads a response body while enforcing MAX_ZIP_DOWNLOAD_BYTES.
    خواندن بدنه پاسخ با رعایت سقف حجم دانلود برای جلوگیری از پر شدن حافظه.
    """
    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_ZIP_DOWNLOAD_BYTES:
        raise ValueError(
            gettext.gettext("Configuration archive is too large to download safely.")
        )

    chunks = []
    total = 0
    while True:
        chunk = response.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_ZIP_DOWNLOAD_BYTES:
            raise ValueError(
                gettext.gettext("Configuration archive exceeds the download size limit.")
            )
        chunks.append(chunk)
    return b"".join(chunks)


def is_safe_path(base_dir: str, path: str, follow_symlinks: bool = True) -> bool:
    """
    Verifies that a resolved target path strictly resides within the base directory.
    Prevents Path Traversal / Zip Slip vulnerabilities.
    بررسی امن بودن مسیر هدف و ممانعت از حملات عبور از دایرکتوری (Zip-Slip).
    """
    matchpath = os.path.realpath(path) if follow_symlinks else os.path.abspath(path)
    return base_dir == os.path.commonpath((base_dir, matchpath))


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
    Pure predicate for the server-list search/filter feature (testable without GTK).
    تابع خالص منطق جستجو/فیلتر لیست سرورها (قابل تست بدون GTK).

    :param name: Configuration filename (e.g. ``iran.ovpn``).
    :param search: Live search text (case-insensitive).
    :param mode: One of ``all``, ``favorites``, ``online``, ``offline``.
    :param favorites: Set of favorite configuration filenames.
    :param latencies: Mapping filename -> RTT in ms (``None`` = unreachable).
    :param proto_mode: One of ``all``, ``tcp``, ``udp``.
    :param protocols: Transports declared by the .ovpn file (``tcp`` / ``udp``).
    :return: True if the server should stay visible.
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

    if proto_mode in ("tcp", "udp") and proto_mode not in (protocols or set()):
        return False
    return True


def download_remote_to_destination(remote: str, destination: str) -> list[str]:
    """
    Downloads or copies OpenVPN configuration files and certificates into the target destination.
    دانلود یا کپی فایل‌های کانفیگ OpenVPN و سرتیفیکیت‌ها به مقصد مورد نظر با رعایت اصول امنیتی.

    :param remote: URL or local filesystem path to a ZIP archive or folder containing .ovpn files.
    :param destination: Destination directory on the local system.
    :return: List of discovered certificate/CA file names.
    """
    ovpn_regex = re.compile(r"\.ovpn$", re.IGNORECASE)
    crt_regex = re.compile(r"(\.crt|\.pem|\.ca|cert)", re.IGNORECASE)

    os.makedirs(destination, exist_ok=True)
    real_destination = os.path.realpath(destination)

    def make_zip_from_bytes(content: bytes) -> zipfile.ZipFile:
        return zipfile.ZipFile(io.BytesIO(content), "r")

    def fetch_zip_archive(src: str) -> zipfile.ZipFile:
        if os.path.exists(src):
            # Enforce the size cap for local files as well
            # اعمال سقف حجم برای فایل‌های محلی نیز
            if os.path.getsize(src) > MAX_ZIP_DOWNLOAD_BYTES:
                raise ValueError(
                    gettext.gettext("Configuration archive is too large to import safely.")
                )
            with open(src, "rb") as f:
                return make_zip_from_bytes(f.read())

        # Validate URL protocol scheme (only HTTP / HTTPS)
        # اعتبارسنجی پروتکل اینترنتی مجاز (تنها HTTP و HTTPS)
        parsed = urllib.parse.urlparse(src)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(gettext.gettext("Invalid URL scheme: only HTTP and HTTPS are permitted."))

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/zip,application/octet-stream,*/*",
            "Connection": "close",
        }
        req = urllib.request.Request(src, headers=headers)
        # Safe opener rejects non-http(s) redirect targets
        # اپنر امن، ریدایرکت به مقصد غیر http(s) را رد می‌کند
        opener = urllib.request.build_opener(_SafeRedirectHandler())
        with opener.open(req, timeout=12.0) as resp:
            return make_zip_from_bytes(_read_limited(resp))

    expanded_remote = os.path.expanduser(remote)

    # 1. Local Folder Import / وارد کردن از پوشه محلی
    if os.path.isdir(expanded_remote):
        found_certs = []
        try:
            entries = os.listdir(expanded_remote)
        except Exception as err:
            logger.error("Failed to read directory %s: %s", expanded_remote, err)
            return []

        for file_name in entries:
            src_file = os.path.join(expanded_remote, file_name)
            if not os.path.isfile(src_file):
                continue
            if file_name.endswith(".ovpn") or file_name.endswith(".crt") or file_name.endswith(".pem"):
                dest_file = os.path.join(real_destination, file_name)
                shutil.copy2(src_file, dest_file)
                if file_name.endswith(".crt") or file_name.endswith(".pem"):
                    found_certs.append(file_name)
        return found_certs

    # 2. ZIP Archive Import / وارد کردن از فایل فشرده ZIP
    try:
        zip_file = fetch_zip_archive(expanded_remote)
    except Exception as exc:
        logger.error("Failed to load ZIP archive from %s: %s", expanded_remote, exc)
        raise NotZipException(
            gettext.gettext(
                "Configuration Source MUST be a valid ZIP archive or accessible folder."
            )
        )

    with zip_file:
        files_in_zip = zip_file.namelist()
        configs = [f for f in files_in_zip if ovpn_regex.search(f)]
        certs = [f for f in files_in_zip if crt_regex.search(f)]
        all_targets = configs + certs

        extracted_certs = []
        extracted_total = 0
        zip_bomb_detected = False

        for file_name in all_targets:
            # Flatten path to prevent directory traversal
            # حذف مسیرهای تودرتو و نامعتبر برای جلوگیری از نفوذ دایرکتوری
            base_name = os.path.basename(file_name)
            if not base_name:
                continue

            target_path = os.path.join(real_destination, base_name)
            if not is_safe_path(real_destination, target_path):
                logger.warning("Skipping potentially unsafe zip entry: %s", file_name)
                continue

            try:
                with zip_file.open(file_name, "r") as source_stream, open(target_path, "wb") as dest_stream:
                    while True:
                        chunk = source_stream.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        dest_stream.write(chunk)
                        extracted_total += len(chunk)
                        # Zip-bomb protection: abort if the uncompressed size explodes
                        # محافظت در برابر بمب فشرده: توقف در صورت انفجار حجم داده غیرفشرده
                        if extracted_total > MAX_EXTRACTED_TOTAL_BYTES:
                            zip_bomb_detected = True
                            logger.error("Extraction aborted: uncompressed size limit exceeded.")
                            break

                if zip_bomb_detected:
                    break

                if crt_regex.search(base_name):
                    extracted_certs.append(base_name)
            except Exception as e:
                logger.error("Error extracting %s: %s", file_name, e)

        if zip_bomb_detected:
            raise NotZipException(
                gettext.gettext("Configuration archive appears to be a zip bomb and was rejected.")
            )

    return extracted_certs


def ovpn_is_auth_required(ovpn_file: str) -> bool:
    """
    Checks whether an .ovpn configuration file specifies 'auth-user-pass'.
    بررسی نیاز فایل کانفیگ به نام کاربری و کلمه عبور.
    """
    try:
        with open(ovpn_file, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
            return "auth-user-pass" in data
    except Exception as e:
        logger.error("Error reading %s: %s", ovpn_file, e)
        return False
