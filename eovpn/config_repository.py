"""
Transactional repository for imported OpenVPN configurations.
مخزن تراکنشی برای کانفیگ‌های واردشده OpenVPN.

A successful update replaces the managed directory only after validation.
Failures restore the previous directory, and a per-path lock prevents two UI
actions from racing over the same staging area.
جایگزینی پوشه مدیریت‌شده فقط پس از اعتبارسنجی کامل انجام می‌شود. در خطا، پوشه
قبلی بازیابی می‌شود و قفل اختصاصی مسیر مانع تداخل دو عملیات رابط کاربری است.
"""

from __future__ import annotations

import gettext
import logging
import os
import shutil
import threading
from pathlib import Path

from .config_import import (
    ImportResult,
    import_configurations,
    make_private_temporary_path,
)

logger = logging.getLogger(__name__)
_ = gettext.gettext

_locks_guard = threading.Lock()
_repository_locks: dict[str, threading.Lock] = {}


class ImportInProgressError(RuntimeError):
    """Raised when the same repository is already updating / خطای اجرای هم‌زمان به‌روزرسانی."""


def _lock_for(path: Path) -> threading.Lock:
    """Returns the process-local lock for a canonical path / قفل محلی مسیر canonical."""
    key = str(path.resolve())
    with _locks_guard:
        return _repository_locks.setdefault(key, threading.Lock())


def _fsync_directory(path: Path) -> None:
    """Persists rename metadata when supported / پایدارسازی متادیتای تغییرنام در صورت پشتیبانی."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        logger.debug("Directory fsync is not supported for %s", path)
    finally:
        os.close(fd)


class ConfigRepository:
    """
    Owns one private directory and updates it transactionally.
    مالک یک پوشه خصوصی و مسئول به‌روزرسانی تراکنشی آن.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.parent = self.root.parent
        self._lock = _lock_for(self.root)

    def ensure(self) -> None:
        """Creates the repository with mode 0700 / ساخت مخزن با مجوز 0700."""
        self.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.parent.chmod(0o700)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root.chmod(0o700)

    def update(self, source: str) -> ImportResult:
        """
        Imports into a unique staging directory and swaps only on success.
        واردکردن در staging یکتا و جابه‌جایی فقط پس از موفقیت کامل.
        """
        if not self._lock.acquire(blocking=False):
            raise ImportInProgressError(_("A configuration update is already in progress."))

        staging = make_private_temporary_path(self.parent, ".staging")
        backup = make_private_temporary_path(self.parent, ".backup")
        moved_old = False
        installed_new = False

        try:
            staging.mkdir(mode=0o700)
            result = import_configurations(source, staging)
            if result.count < 1:
                # Defensive invariant; import_configurations already enforces this.
                # شرط دفاعی؛ تابع import_configurations نیز این مورد را کنترل می‌کند.
                raise RuntimeError(_("The imported source contains no usable configuration."))

            if self.root.exists():
                os.replace(self.root, backup)
                moved_old = True
            try:
                os.replace(staging, self.root)
                installed_new = True
                _fsync_directory(self.parent)
            except Exception:
                if moved_old and backup.exists() and not self.root.exists():
                    os.replace(backup, self.root)
                    moved_old = False
                    _fsync_directory(self.parent)
                raise

            self.root.chmod(0o700)
            if backup.exists():
                try:
                    shutil.rmtree(backup)
                    moved_old = False
                except OSError as exc:
                    # The new repository is valid; a stale backup is safer than
                    # reporting a false import failure.
                    # مخزن جدید معتبر است؛ باقی‌ماندن نسخه پشتیبان از گزارش خطای
                    # کاذب برای عملیات واردکردن امن‌تر است.
                    logger.warning("Could not remove old configuration backup %s: %s", backup, exc)
            return result
        finally:
            if staging.exists():
                try:
                    shutil.rmtree(staging)
                except OSError as exc:
                    logger.warning("Could not remove staging directory %s: %s", staging, exc)

            if moved_old and not installed_new and backup.exists() and not self.root.exists():
                try:
                    os.replace(backup, self.root)
                    moved_old = False
                    _fsync_directory(self.parent)
                except OSError as exc:
                    # Never delete the only remaining copy; leave its path in the log.
                    # تنها نسخه باقی‌مانده هرگز حذف نمی‌شود و مسیر آن در لاگ ثبت می‌گردد.
                    logger.critical(
                        "Automatic configuration rollback failed; backup retained at %s: %s",
                        backup,
                        exc,
                    )
            self._lock.release()
