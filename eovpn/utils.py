"""
eOVPN-Pro Utility Functions & Configuration Handlers
توابع کمکی و پردازش فایل‌های پیکربندی در eOVPN-Pro

Provides safe ZIP extraction (Zip-Slip protection), remote configuration downloads,
and certificate extraction utilities.
شامل استخراج امن فایل‌های فشرده (محافظت در برابر Zip-Slip)، دانلود کانفیگ‌ها و استخراج گواهی‌ها.
"""

import os
import io
import re
import shutil
import logging
import zipfile
import urllib.request
import urllib.parse
import gettext
from pathlib import Path

logger = logging.getLogger(__name__)


class NotZipException(Exception):
    """
    Exception raised when the provided configuration archive is invalid.
    استثنای مربوط به نامعتبر بودن فایل فشرده کانفیگ.
    """
    pass


def is_safe_path(base_dir: str, path: str, follow_symlinks: bool = True) -> bool:
    """
    Verifies that a resolved target path strictly resides within the base directory.
    Prevents Path Traversal / Zip Slip vulnerabilities.
    بررسی امن بودن مسیر هدف و ممانعت از حملات عبور از دایرکتوری (Zip-Slip).
    """
    matchpath = os.path.realpath(path) if follow_symlinks else os.path.abspath(path)
    return base_dir == os.path.commonpath((base_dir, matchpath))


def download_remote_to_destination(remote: str, destination: str) -> list[str]:
    """
    Downloads or copies OpenVPN configuration files and certificates into the target destination.
    دانلود یا کپی فایل‌های کانفیگ OpenVPN و سرتیفیکیت‌ها به مقصد مورد نظر با رعایت اصول امنیتی.

    :param remote: URL or local filesystem path to a ZIP archive or folder containing .ovpn files.
    :param destination: Destination directory on the local system.
    :return: List of discovered certificate/CA file names.
    """
    ovpn_regex = re.compile(r'\.ovpn$', re.IGNORECASE)
    crt_regex = re.compile(r'(\.crt|\.pem|\.ca|cert)', re.IGNORECASE)

    os.makedirs(destination, exist_ok=True)
    real_destination = os.path.realpath(destination)

    def make_zip_from_bytes(content: bytes) -> zipfile.ZipFile:
        return zipfile.ZipFile(io.BytesIO(content), "r")

    def fetch_zip_archive(src: str) -> zipfile.ZipFile:
        if os.path.exists(src):
            with open(src, "rb") as f:
                return make_zip_from_bytes(f.read())
        else:
            # Validate URL protocol scheme (only HTTP / HTTPS)
            # اعتبارسنجی پروتکل اینترنتی مجاز (تنها HTTP و HTTPS)
            parsed = urllib.parse.urlparse(src)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(gettext.gettext("Invalid URL scheme: only HTTP and HTTPS are permitted."))

            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/zip,application/octet-stream,*/*',
                'Connection': 'close'
            }
            req = urllib.request.Request(src, headers=headers)
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                return make_zip_from_bytes(resp.read())

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
            if file_name.endswith('.ovpn') or file_name.endswith('.crt') or file_name.endswith('.pem'):
                dest_file = os.path.join(real_destination, file_name)
                shutil.copy2(src_file, dest_file)
                if file_name.endswith('.crt') or file_name.endswith('.pem'):
                    found_certs.append(file_name)
        return found_certs

    # 2. ZIP Archive Import / وارد کردن از فایل فشرده ZIP
    try:
        zip_file = fetch_zip_archive(expanded_remote)
    except Exception as exc:
        logger.error("Failed to load ZIP archive from %s: %s", expanded_remote, exc)
        raise NotZipException(gettext.gettext("Configuration Source MUST be a valid ZIP archive or accessible folder."))

    with zip_file:
        files_in_zip = zip_file.namelist()
        configs = [f for f in files_in_zip if ovpn_regex.search(f)]
        certs = [f for f in files_in_zip if crt_regex.search(f)]
        all_targets = configs + certs

        extracted_certs = []
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
                    shutil.copyfileobj(source_stream, dest_stream)

                if crt_regex.search(base_name):
                    extracted_certs.append(base_name)
            except Exception as e:
                logger.error("Error extracting %s: %s", file_name, e)

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
