"""
Secure OpenVPN configuration importer.
واردکننده امن پیکربندی‌های OpenVPN.

Remote sources are HTTPS-only. Archives are bounded by compressed size,
uncompressed size, entry count, and compression ratio. Imported files are
created with mode 0600 inside a 0700 directory.
منابع راه‌دور فقط از HTTPS پذیرفته می‌شوند. تعداد ورودی‌ها، حجم فشرده و
غیرفشرده و نسبت فشرده‌سازی آرشیو محدود است. فایل‌ها با مجوز 0600 در پوشه‌ای
با مجوز 0700 ساخته می‌شوند.
"""

from __future__ import annotations

import gettext
import io
import logging
import os
import shutil
import stat
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)
_ = gettext.gettext

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_EXTRACTED_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 4096
MAX_COMPRESSION_RATIO = 250
CHUNK_SIZE = 64 * 1024

CONFIG_EXTENSIONS = frozenset({".ovpn"})
ASSET_EXTENSIONS = frozenset(
    {
        ".ca",
        ".cer",
        ".crt",
        ".key",
        ".p12",
        ".pem",
        ".pfx",
        ".pkcs12",
        ".ta",
    }
)


class ConfigurationImportError(Exception):
    """Base import error / خطای پایه واردکردن کانفیگ."""


class InsecureSourceError(ConfigurationImportError):
    """Raised for non-HTTPS remote sources / خطای منبع راه‌دور ناامن."""


class ArchiveLimitError(ConfigurationImportError):
    """Raised when an archive exceeds a security limit / خطای عبور از محدودیت امنیتی."""


class NoConfigurationsError(ConfigurationImportError):
    """Raised when no usable .ovpn file exists / خطای نبود فایل قابل‌استفاده .ovpn."""


@dataclass(frozen=True)
class ImportResult:
    """Immutable summary of an import / خلاصه تغییرناپذیر نتیجه واردکردن."""

    configs: tuple[str, ...]
    assets: tuple[str, ...]
    certificates: tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.configs)


class HTTPSOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Rejects every redirect that leaves HTTPS / رد هر ریدایرکت خارج از HTTPS."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme.lower() != "https":
            raise InsecureSourceError(
                _("Unsafe redirect blocked: configuration downloads must remain on HTTPS.")
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _ensure_private_directory(path: Path) -> None:
    """Creates a private destination directory / ساخت پوشه مقصد خصوصی."""
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def _read_limited(stream, limit: int = MAX_ARCHIVE_BYTES) -> bytes:
    """Reads at most ``limit`` bytes / خواندن جریان حداکثر تا سقف تعیین‌شده."""
    content_length = stream.headers.get("Content-Length") if hasattr(stream, "headers") else None
    if content_length and content_length.isdigit() and int(content_length) > limit:
        raise ArchiveLimitError(_("Configuration archive is too large to download safely."))

    chunks: list[bytes] = []
    total = 0
    while chunk := stream.read(CHUNK_SIZE):
        total += len(chunk)
        if total > limit:
            raise ArchiveLimitError(_("Configuration archive exceeds the download size limit."))
        chunks.append(chunk)
    return b"".join(chunks)


def _download_https(url: str) -> bytes:
    """Downloads an archive over verified HTTPS / دانلود آرشیو روی HTTPS اعتبارسنجی‌شده."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise InsecureSourceError(_("Remote configuration sources must use a valid HTTPS URL."))

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "eOVPN-Pro/1.5",
            "Accept": "application/zip,application/octet-stream",
            "Connection": "close",
        },
    )
    opener = urllib.request.build_opener(HTTPSOnlyRedirectHandler())
    with opener.open(request, timeout=15.0) as response:
        return _read_limited(response)


def _is_allowed_file(name: str) -> tuple[bool, bool]:
    """Returns (allowed, is_config) for a basename / تشخیص نوع فایل مجاز."""
    suffix = Path(name).suffix.lower()
    is_config = suffix in CONFIG_EXTENSIONS
    return is_config or suffix in ASSET_EXTENSIONS, is_config


def _safe_basename(raw_name: str) -> str:
    """
    Returns a portable basename and rejects traversal-like names.
    بازگرداندن نام پایه قابل‌حمل و رد نام‌های شبیه عبور از مسیر.
    """
    normalized = raw_name.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ConfigurationImportError(_("Archive contains an unsafe file path."))
    basename = parts[-1]
    if basename in (".", "..") or "\x00" in basename:
        raise ConfigurationImportError(_("Archive contains an invalid filename."))
    return basename


def _secure_copy_stream(source, destination: Path, budget: list[int]) -> None:
    """
    Copies one file with O_EXCL/O_NOFOLLOW and mode 0600.
    کپی یک فایل با O_EXCL/O_NOFOLLOW و مجوز 0600.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=True) as output:
            while chunk := source.read(CHUNK_SIZE):
                budget[0] += len(chunk)
                if budget[0] > MAX_EXTRACTED_BYTES:
                    raise ArchiveLimitError(
                        _("Configuration source exceeds the extracted size limit.")
                    )
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        destination.chmod(0o600)
    except Exception:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            logger.debug("Could not remove partial import file: %s", destination)
        raise


def _build_result(configs: list[str], assets: list[str]) -> ImportResult:
    """Validates and normalizes an import result / اعتبارسنجی و یکسان‌سازی نتیجه."""
    if not configs:
        raise NoConfigurationsError(_("No usable OpenVPN configuration was found in the source."))
    configs_sorted = tuple(sorted(configs, key=str.casefold))
    assets_sorted = tuple(sorted(assets, key=str.casefold))
    certificates = tuple(
        name for name in assets_sorted if Path(name).suffix.lower() in {".ca", ".cer", ".crt", ".pem"}
    )
    return ImportResult(configs_sorted, assets_sorted, certificates)


def _import_zip(archive: zipfile.ZipFile, destination: Path) -> ImportResult:
    """Extracts an allowlisted ZIP transactionally into an empty directory."""
    entries = archive.infolist()
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise ArchiveLimitError(_("Configuration archive contains too many entries."))

    selected: list[tuple[zipfile.ZipInfo, str, bool]] = []
    seen: set[str] = set()
    declared_total = 0

    for info in entries:
        if info.is_dir():
            continue
        mode = info.external_attr >> 16
        if mode and not stat.S_ISREG(mode) and stat.S_IFMT(mode) != 0:
            raise ConfigurationImportError(_("Archive contains a non-regular file."))

        basename = _safe_basename(info.filename)
        allowed, is_config = _is_allowed_file(basename)
        if not allowed:
            continue
        folded = basename.casefold()
        if folded in seen:
            raise ConfigurationImportError(_("Archive contains duplicate filenames."))
        seen.add(folded)

        if info.flag_bits & 0x1:
            raise ConfigurationImportError(_("Encrypted ZIP entries are not supported."))
        declared_total += info.file_size
        if declared_total > MAX_EXTRACTED_BYTES:
            raise ArchiveLimitError(_("Configuration archive expands beyond the safe size limit."))
        if info.file_size > 1024 * 1024:
            compressed = max(1, info.compress_size)
            if info.file_size / compressed > MAX_COMPRESSION_RATIO:
                raise ArchiveLimitError(_("Configuration archive has an unsafe compression ratio."))
        selected.append((info, basename, is_config))

    configs: list[str] = []
    assets: list[str] = []
    budget = [0]
    for info, basename, is_config in selected:
        target = destination / basename
        try:
            with archive.open(info, "r") as source:
                _secure_copy_stream(source, target, budget)
        except (ConfigurationImportError, ArchiveLimitError):
            raise
        except Exception as exc:
            raise ConfigurationImportError(
                _("Failed to extract configuration file: {}.").format(basename)
            ) from exc
        (configs if is_config else assets).append(basename)

    return _build_result(configs, assets)


def _import_local_directory(source: Path, destination: Path) -> ImportResult:
    """Copies allowlisted regular files from a local tree / کپی فایل‌های مجاز از پوشه محلی."""
    candidates: list[tuple[Path, str, bool]] = []
    seen: set[str] = set()

    for root, directories, filenames in os.walk(source, followlinks=False):
        directories[:] = sorted(
            name for name in directories if not (Path(root) / name).is_symlink()
        )
        for filename in sorted(filenames):
            path = Path(root) / filename
            if path.is_symlink() or not path.is_file():
                continue
            basename = _safe_basename(filename)
            allowed, is_config = _is_allowed_file(basename)
            if not allowed:
                continue
            folded = basename.casefold()
            if folded in seen:
                raise ConfigurationImportError(_("Local source contains duplicate filenames."))
            seen.add(folded)
            candidates.append((path, basename, is_config))

    configs: list[str] = []
    assets: list[str] = []
    budget = [0]
    for path, basename, is_config in candidates:
        with path.open("rb") as source_stream:
            _secure_copy_stream(source_stream, destination / basename, budget)
        (configs if is_config else assets).append(basename)

    return _build_result(configs, assets)


def import_configurations(source: str, destination: str | Path) -> ImportResult:
    """
    Imports a local directory, local ZIP, or HTTPS ZIP into ``destination``.
    واردکردن پوشه محلی، ZIP محلی یا ZIP مبتنی بر HTTPS به مسیر مقصد.
    """
    if not source or not str(source).strip():
        raise ConfigurationImportError(_("Configuration source is empty."))

    destination_path = Path(destination).expanduser().resolve()
    _ensure_private_directory(destination_path)
    expanded = Path(os.path.expanduser(str(source))).resolve()

    if expanded.is_dir():
        return _import_local_directory(expanded, destination_path)

    try:
        if expanded.is_file():
            if expanded.stat().st_size > MAX_ARCHIVE_BYTES:
                raise ArchiveLimitError(_("Configuration archive is too large to import safely."))
            archive_bytes = expanded.read_bytes()
        else:
            archive_bytes = _download_https(str(source).strip())
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            return _import_zip(archive, destination_path)
    except ConfigurationImportError:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ConfigurationImportError(
            _("Configuration source must be a valid ZIP archive or a local folder.")
        ) from exc
    except OSError as exc:
        raise ConfigurationImportError(_("Could not read the configuration source.")) from exc


def make_private_temporary_path(parent: Path, suffix: str = "") -> Path:
    """
    Reserves a private, unpredictable path for repository transactions.
    رزرو مسیر خصوصی و غیرقابل‌پیش‌بینی برای تراکنش مخزن کانفیگ.
    """
    _ensure_private_directory(parent)
    return parent / f".eovpn-{uuid4().hex}{suffix}"


def remove_tree(path: Path) -> None:
    """Removes a private transaction tree / حذف پوشه موقت تراکنش."""
    if path.exists():
        shutil.rmtree(path, ignore_errors=False)
