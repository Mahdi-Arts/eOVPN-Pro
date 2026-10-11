"""
eOVPN-Pro Connection Manager Module
ماژول مدیریت اتصال VPN در eOVPN-Pro

Provides an abstract interface and concrete implementations for connecting,
disconnecting, and monitoring VPN tunnels via NetworkManager and OpenVPN 3 Linux.

ارائه‌دهنده ساختار انتزاعی و پیاده‌سازی‌های عملیاتی برای مدیریت تونل‌های
OpenVPN از طریق NetworkManager و OpenVPN 3.

Backend native bindings are imported defensively. The application can therefore
be imported, tested and configured even when one backend's CFFI module is not
available; instantiation fails with a clear error only when that backend is
actually selected.

بایندینگ‌های بومی به‌صورت تدافعی ایمپورت می‌شوند تا برنامه حتی در صورت نبود یکی
از بک‌اندها قابل ایمپورت/تست/پیکربندی باشد و فقط هنگام استفاده از همان بک‌اند،
خطای شفاف دریافت شود.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Secret", "1")
from gi.repository import GLib, Secret

from .backend._base import CFFIStringMixin, cffi_string
from .eovpn_base import Base
from .utils import audit_ovpn_content

logger = logging.getLogger(__name__)


class OperationCancelled(RuntimeError):
    """Raised internally when a native worker is cancelled cooperatively."""


def _secure_temp_dir() -> str | None:
    """
    Returns the most private directory available for short-lived credential files.

    ``$XDG_RUNTIME_DIR`` is created by the login manager as a user-owned
    ``0700`` directory on a tmpfs that is wiped at logout, which makes it a far
    better home for a config file containing an inline ``<ca>`` block than the
    world-readable ``/tmp``. A dedicated ``eovpn-pro`` sub-directory keeps our
    artefacts separated from other applications. When the variable is unset or
    unusable (minimal containers, some cron-like sessions) the function returns
    ``None`` so the caller falls back to the platform default.

    محرمانه‌ترین پوشهٔ در دسترس برای فایل‌های موقت حاوی اطلاعات حساس را
    برمی‌گرداند.

    مقدار `$XDG_RUNTIME_DIR` را مدیر ورود سیستم به‌صورت پوشه‌ای با مالکیت کاربر و
    مجوز `0700` روی tmpfs می‌سازد که هنگام خروج از حساب پاک می‌شود؛ بنابراین برای
    نگهداری فایل کانفیگی که بلوک درون‌خطی `<ca>` دارد بسیار مناسب‌تر از `/tmp`
    است که برای همه قابل خواندن است. یک زیرپوشهٔ اختصاصی `eovpn-pro` نیز فایل‌های
    ما را از سایر برنامه‌ها جدا نگه می‌دارد. اگر این متغیر تعریف یا قابل استفاده
    نباشد (کانتینرهای کمینه و برخی نشست‌های غیرتعاملی)، مقدار `None` برگردانده
    می‌شود تا فراخوان به مسیر پیش‌فرض سیستم بازگردد.

    :return: Path of the private directory, or ``None``.
             مسیر پوشهٔ خصوصی، یا ``None``.
    """
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir or not os.path.isdir(runtime_dir):
        return None

    private_dir = os.path.join(runtime_dir, "eovpn-pro")
    try:
        os.makedirs(private_dir, mode=0o700, exist_ok=True)
        # Re-assert the mode: makedirs() honours the umask on creation and
        # leaves a pre-existing directory untouched.
        # اعمال مجدد مجوز: makedirs هنگام ساخت تابع umask است و پوشهٔ از پیش
        # موجود را تغییر نمی‌دهد.
        os.chmod(private_dir, 0o700)
    except OSError as error:
        logger.debug("XDG_RUNTIME_DIR unusable (%s); falling back to system temp.", error)
        return None

    return private_dir


_NM_IMPORT_ERROR: Exception | None = None
_OVPN3_IMPORT_ERROR: Exception | None = None
NMDbus: Any = None
OVPN3Dbus: Any = None
_libeovpn_nm: Any = None
_libopenvpn3: Any = None

try:
    from .backend.networkmanager import _libeovpn_nm as _nm_lib  # type: ignore[attr-defined]
    from .backend.networkmanager.dbus import NMDbus as _NMDbus

    _libeovpn_nm = _nm_lib
    NMDbus = _NMDbus
except Exception as exc:  # pragma: no cover - depends on native build/runtime
    _NM_IMPORT_ERROR = exc
    logger.warning("NetworkManager backend module unavailable: %s", exc)

try:
    from .backend.openvpn3 import _libopenvpn3 as _ovpn3_lib  # type: ignore[attr-defined]
    from .backend.openvpn3.dbus import OVPN3Dbus as _OVPN3Dbus

    _libopenvpn3 = _ovpn3_lib
    OVPN3Dbus = _OVPN3Dbus
except Exception as exc:  # pragma: no cover - depends on native build/runtime
    _OVPN3_IMPORT_ERROR = exc
    logger.warning("OpenVPN 3 backend module unavailable: %s", exc)


class ConnectionManager(ABC, Base):
    """
    Abstract base class for VPN connection managers.
    کلاس پایه انتزاعی برای مدیریت‌کننده‌های اتصال VPN.
    """

    def __init__(self, name: str):
        super().__init__()
        self.__NAME__ = name

    @abstractmethod
    def get_name(self) -> str:
        """Returns the identifier name of the backend."""

    @abstractmethod
    def start_watch(self):
        """Subscribes to connection state change events."""

    @abstractmethod
    def version(self) -> str | None:
        """Returns backend version string."""

    @abstractmethod
    def connect(self, openvpn_config: str):
        """Initiates VPN connection using the provided configuration file."""

    @abstractmethod
    def disconnect(self):
        """Terminates active VPN connection."""

    @abstractmethod
    def status(self) -> bool:
        """Checks if a VPN tunnel is currently active."""


def available_backend_names() -> set[str]:
    """
    Returns the identifiers of backends whose native bindings loaded successfully.

    شناسه بک‌اندهایی که بایندینگ بومی آن‌ها با موفقیت بارگذاری شده است را برمی‌گرداند.
    """
    available: set[str] = set()
    if _libeovpn_nm is not None:
        available.add("networkmanager")
    if _libopenvpn3 is not None:
        available.add("openvpn3")
    return available


def backend_diagnostics() -> dict[str, str]:
    """Return safe, user-facing availability diagnostics for each backend."""
    diagnostics: dict[str, str] = {}
    if _libeovpn_nm is not None:
        diagnostics["networkmanager"] = "available"
    elif _NM_IMPORT_ERROR is not None:
        diagnostics["networkmanager"] = str(_NM_IMPORT_ERROR)
    else:
        diagnostics["networkmanager"] = "native bindings are unavailable"

    if _libopenvpn3 is not None:
        diagnostics["openvpn3"] = "available"
    elif _OVPN3_IMPORT_ERROR is not None:
        diagnostics["openvpn3"] = str(_OVPN3_IMPORT_ERROR)
    else:
        diagnostics["openvpn3"] = "native bindings are unavailable"
    return diagnostics


def backend_capabilities() -> dict[str, dict[str, object]]:
    """Return backend capabilities for the settings UI without starting a backend."""
    available = available_backend_names()

    def safe_probe(probe, default=None):
        """Keep optional capability probes from turning Settings into a crash path."""
        try:
            return probe()
        except Exception as exc:  # pragma: no cover - depends on host native bindings
            logger.debug("Backend capability probe failed: %s", exc)
            return default

    networkmanager_version = safe_probe(NetworkManager.probe_version)
    networkmanager_plugin = safe_probe(NetworkManager.probe_openvpn_plugin)
    networkmanager_cffi = safe_probe(NetworkManager.probe_cffi_contract, "unavailable")
    openvpn3_version = safe_probe(OpenVPN3.probe_version)
    return {
        "networkmanager": {
            "available": "networkmanager" in available,
            "version": networkmanager_version,
            "openvpn_plugin": networkmanager_plugin,
            "cffi_contract": networkmanager_cffi,
            "native_bindings": "networkmanager" in available,
            "reason": backend_diagnostics()["networkmanager"],
        },
        "openvpn3": {
            "available": "openvpn3" in available,
            "version": openvpn3_version,
            "dco": "openvpn3" in available,
            "native_bindings": "openvpn3" in available,
            "reason": backend_diagnostics()["openvpn3"],
        },
    }


def create_connection_manager(callback, preferred: str | None = None):
    """
    Creates a backend instance, preferring ``preferred`` when it is available.

    If an explicitly selected backend is unavailable, fail clearly instead of
    silently switching the user's backend. Raises ``RuntimeError`` when no
    backend is available.

    یک نمونه بک‌اند می‌سازد و در صورت موجود بودن، ``preferred`` را اولویت می‌دهد.
    اگر بک‌اند درخواست‌شده صریحاً انتخاب شده ولی در دسترس نباشد، خطای شفاف برمی‌گرداند؛
    فقط در حالت انتخاب‌نشدن بک‌اند، ترتیب پیش‌فرض موجود بررسی می‌شود.
    اگر هیچ بک‌اندی موجود نباشد، ``RuntimeError`` پرتاب می‌کند.
    """
    available = available_backend_names()
    if not available:
        details = "; ".join(f"{name}: {reason}" for name, reason in backend_diagnostics().items())
        raise RuntimeError(
            "No VPN backend is available. Install/network-manager-openvpn and "
            f"build the native bindings. Diagnostics: {details}"
        )

    if preferred and preferred not in available:
        reason = backend_diagnostics().get(preferred, "backend is not recognized")
        raise RuntimeError(f"Selected VPN backend '{preferred}' is unavailable: {reason}")

    order: list[str] = []
    if preferred in available:
        order.append(preferred)
    order.extend(name for name in ("networkmanager", "openvpn3") if name in available and name not in order)

    last_error: Exception | None = None
    for name in order:
        try:
            if name == "networkmanager":
                return NetworkManager(callback)
            return OpenVPN3(callback)
        except Exception as exc:
            last_error = exc
            logger.warning("Failed to initialize %s backend: %s", name, exc)
    raise RuntimeError(f"Unable to initialize any VPN backend: {last_error}")


class NetworkManager(CFFIStringMixin, ConnectionManager):
    """
    NetworkManager backend implementation using libnm via CFFI and D-Bus signals.
    پیاده‌سازی بک‌اند NetworkManager با استفاده از libnm، CFFI و سیگنال‌های D-Bus.
    """

    def __init__(self, callback):
        super().__init__("NetworkManager")
        if _libeovpn_nm is None:
            raise RuntimeError(
                "NetworkManager native bindings are unavailable. Build with "
                "Meson/Ninja and install network-manager-openvpn."
            ) from _NM_IMPORT_ERROR

        self.uuid = None
        self.nm_manager = _libeovpn_nm.lib
        self.ffi = _libeovpn_nm.ffi
        self.callback = callback
        self._temp_config_path: str | None = None
        # Native operations are serialized instead of being dropped when a
        # timeout races with disconnect/next-candidate.  The old non-blocking
        # lock silently discarded the follow-up operation, leaving cascade
        # auto-connect stuck after its countdown reached zero.
        # عملیات بومی به‌جای حذف‌شدن در اثر race بین timeout و قطع/کاندید بعدی،
        # به‌صورت ترتیبی صف می‌شوند؛ قفل قبلی عملیات بعدی را بی‌صدا دور می‌ریخت.
        self._operation_state_lock = threading.Lock()
        self._operation_queue: deque[tuple[Callable[..., None], tuple[Any, ...]]] = deque()
        self._operation_cancel = threading.Event()
        self._suppress_callbacks = threading.Event()
        self._worker_thread: threading.Thread | None = None

        self.dbus = NMDbus() if NMDbus is not None else None
        self.watch = False

    @classmethod
    def probe_version(cls) -> str | None:
        """
        Reads the NetworkManager version without instantiating the backend,
        so the settings window never pays for a full probe on the UI thread.

        خواندن نسخه NetworkManager بدون نمونه‌سازی بک‌اند؛ تا پنجره تنظیمات
        هزینه پروب کامل را روی نخ UI نپردازد.
        """
        if _libeovpn_nm is None:
            return None
        return cffi_string(_libeovpn_nm.ffi, _libeovpn_nm.lib.get_version(), True)  # type: ignore[return-value]

    @classmethod
    def probe_cffi_contract(cls) -> str:
        """Return whether the loaded native module exposes the current API."""
        if _libeovpn_nm is None:
            return "unavailable"
        required = ("add_connection", "activate_connection", "get_last_error")
        if all(hasattr(_libeovpn_nm.lib, symbol) for symbol in required):
            return "current"
        return "legacy"

    @classmethod
    def probe_openvpn_plugin(cls) -> bool | None:
        """Read OpenVPN plugin capability without creating a backend instance."""
        if _libeovpn_nm is None or not hasattr(_libeovpn_nm.lib, "is_openvpn_plugin_available"):
            return None
        try:
            return bool(_libeovpn_nm.lib.is_openvpn_plugin_available())
        except Exception as exc:  # pragma: no cover - depends on host libnm
            logger.debug("Could not probe NetworkManager OpenVPN plugin: %s", exc)
            return None

    def get_name(self) -> str:
        return "networkmanager"

    def start_watch(self):
        self._suppress_callbacks.clear()
        if not self.watch and self.dbus is not None:
            self.dbus.watch(self._guarded_callback)
            self.watch = True

    def _guarded_callback(self, *args) -> None:
        """Drop late native signals after an explicit operation cancellation."""
        if self._suppress_callbacks.is_set():
            logger.debug("Ignoring late NetworkManager callback after cancellation.")
            return
        if self.callback is not None:
            self.callback(*args)

    def stop_watch(self):
        """
        Unsubscribes from NetworkManager D-Bus signals.
        لغو اشتراک سیگنال‌های D-Bus شبکه.
        """
        if self.watch and self.dbus is not None:
            try:
                self.dbus.remove_watch()
            finally:
                self.watch = False

    def connect(self, openvpn_config: str):
        """
        Creates and activates a NetworkManager OpenVPN connection securely.

        The blocking libnm work runs on a short-lived worker thread: every C
        call still carries its own 15-second watchdog, but the GTK main loop
        is never frozen by a nested GMainLoop.

        ایجاد و فعال‌سازی امن کانکشن در NetworkManager.
        کار مسدودکننده libnm روی یک نخ کارگر کوتاه‌عمر اجرا می‌شود؛ هر فراخوانی C
        همچنان نگهبان ۱۵ ثانیه‌ای خود را دارد اما حلقه اصلی GTK هرگز توسط
        GMainLoop تودرتو فریز نمی‌شود.
        """
        suspicious = audit_ovpn_content(openvpn_config)
        if suspicious:
            message = "Refusing to connect an untrusted profile containing: " + ", ".join(suspicious)
            logger.warning(message)
            if self.callback is not None:
                GLib.idle_add(self._guarded_callback, False, message)
            return
        self._dispatch_off_ui_thread(self._connect_blocking, openvpn_config)

    def cancel_current_operation(self) -> None:
        """Request cooperative cancellation and suppress stale callbacks."""
        self._operation_cancel.set()
        self._suppress_callbacks.set()
        with self._operation_state_lock:
            self._operation_queue.clear()

    def _raise_if_cancelled(self) -> None:
        if self._operation_cancel.is_set():
            raise OperationCancelled("NetworkManager operation cancelled")

    def _native_error(self, fallback: str) -> str:
        """Read the optional structured error exposed by the CFFI boundary."""
        getter = getattr(self.nm_manager, "get_last_error", None)
        if getter is not None:
            try:
                message = self.to_cffi_string(getter(), True)
                if message:
                    return str(message)
            except Exception as exc:
                logger.debug("Could not read native NetworkManager error: %s", exc)
        return fallback

    def _dispatch_off_ui_thread(self, operation, *args) -> None:
        """
        Runs native operations in order on a daemon worker thread.

        A timeout may request disconnect while the preceding connect call is
        still unwinding.  Queueing preserves that required ordering; dropping
        the request leaves the UI on a finished countdown with no next
        candidate.

        هر بار فقط یک عملیات بومی را روی نخ کارگر daemon اجرا می‌کند؛ قفل باعث
        می‌شود درخواست‌های همپوشان به‌جای رقابت روی وضعیت libnm، نادیده گرفته شوند.
        """
        with self._operation_state_lock:
            self._operation_queue.append((operation, args))
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return

            thread = threading.Thread(target=self._operation_runner, name="eovpn-nm-op", daemon=True)
            self._worker_thread = thread
            thread.start()

    def _operation_runner(self) -> None:
        """Drain native operations without dropping timeout follow-ups."""
        while True:
            with self._operation_state_lock:
                if not self._operation_queue:
                    self._worker_thread = None
                    return
                operation, args = self._operation_queue.popleft()
                self._operation_cancel.clear()
                self._suppress_callbacks.clear()
                cancel_event = self._operation_cancel

            try:
                operation(*args)
            except OperationCancelled:
                logger.info("NetworkManager native operation cancelled.")
            except Exception as exc:
                logger.error("NetworkManager native operation failed: %s", exc)
                if self.callback is not None and not cancel_event.is_set():
                    message = str(exc) or "NetworkManager operation failed."

                    def notify_failure() -> bool:
                        try:
                            self.callback(False, message)
                        except Exception:
                            logger.exception("Failed to deliver NetworkManager error to the UI.")
                        return False

                    GLib.idle_add(notify_failure)

    def _connect_blocking(self, openvpn_config: str):
        """Worker body of :meth:`connect` / بدنه نخ کارگر متد connect."""
        self._raise_if_cancelled()
        nm_username = self.get_setting(self.SETTING.AUTH_USER)
        nm_password = None
        nm_ca = self.get_setting(self.SETTING.CA)

        if nm_username is not None:
            try:
                nm_password = Secret.password_lookup_sync(
                    self.EOVPN_SECRET_SCHEMA,
                    {"username": nm_username},
                    None,
                )
            except Exception as e:
                logger.debug("Secret service lookup error: %s", e)
                nm_password = self.get_session_password()

        # Secure temporary file: private runtime directory, unique name and
        # explicit 0600. The file briefly holds the CA material, so it is kept
        # out of the shared /tmp whenever XDG_RUNTIME_DIR is available.
        # فایل موقت امن: پوشهٔ اجرای خصوصی، نام یکتا و مجوز صریح 0600. این فایل
        # برای مدت کوتاهی محتوای CA را نگه می‌دارد، بنابراین تا وقتی
        # XDG_RUNTIME_DIR در دسترس باشد از پوشهٔ اشتراکی /tmp دور نگه داشته می‌شود.
        fd, tmp_path = tempfile.mkstemp(suffix=".ovpn", dir=_secure_temp_dir(), text=True)
        self._temp_config_path = tmp_path
        try:
            os.chmod(tmp_path, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                with open(openvpn_config, encoding="utf-8", errors="ignore") as f:
                    tmp_file.write(f.read() + "\n")

                if nm_ca is not None and os.path.exists(nm_ca):
                    with open(nm_ca, encoding="utf-8", errors="ignore") as caf:
                        tmp_file.write(f"\n<ca>\n{caf.read()}\n</ca>\n")
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            self._temp_config_path = None
            raise

        try:
            self._raise_if_cancelled()
            uuid = self.nm_manager.add_connection(
                self._temp_config_path.encode("utf-8"),
                (nm_username.encode("utf-8") if nm_username is not None else None),
                (nm_password.encode("utf-8") if nm_password is not None else None),
                self.ffi.NULL,
            )
            self.uuid = self.to_cffi_string(uuid)
            if not self.uuid:
                raise RuntimeError(self._native_error("NetworkManager could not import the VPN profile."))
            self._raise_if_cancelled()
            activated = self.nm_manager.activate_connection(self.uuid)
            if not activated:
                raise RuntimeError(
                    self._native_error("NetworkManager rejected activation of the VPN profile.")
                )
            if self._operation_cancel.is_set():
                self.nm_manager.disconnect(self.uuid)
                self.nm_manager.delete_connection(self.uuid)
                self.uuid = None
                raise OperationCancelled("NetworkManager connection cancelled")
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, self.uuid.decode("utf-8"))
        finally:
            if self._temp_config_path and os.path.exists(self._temp_config_path):
                try:
                    os.remove(self._temp_config_path)
                except Exception as ex:
                    logger.warning("Failed to remove temp config file: %s", ex)
                self._temp_config_path = None

    def disconnect(self):
        """
        Deactivates and removes this backend's VPN profile (worker thread).

        قطع اتصال و حذف پروفایل VPN مربوط به این بک‌اند (روی نخ کارگر).
        """
        self._dispatch_off_ui_thread(self._disconnect_blocking)

    def _disconnect_blocking(self):
        """Worker body of :meth:`disconnect` / بدنه نخ کارگر متد disconnect."""
        if self.uuid is None:
            for _ in range(3):
                active_uuid = self.to_cffi_string(self.nm_manager.get_eovpn_active_vpn_connection_uuid())
                if not active_uuid:
                    break
                self.nm_manager.disconnect(active_uuid)
            return

        is_uuid_found = self.nm_manager.is_vpn_activated(self.uuid)
        if is_uuid_found != -1:
            logger.info("Disconnecting NetworkManager VPN UUID (%s).", self.uuid)
            self.nm_manager.disconnect(self.uuid)
            self.nm_manager.delete_connection(self.uuid)
            self.uuid = None
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, None)

    def status(self) -> bool:
        return bool(self.nm_manager.is_vpn_running())

    def delete_all_connections(self):
        """Deletes only profiles marked as managed by eOVPN-Pro."""
        self.nm_manager.delete_all_vpn_connections()

    def version(self) -> str | None:
        ver = self.nm_manager.get_version()
        return self.to_cffi_string(ver, True)

    def is_openvpn_plugin_available(self) -> bool:
        return bool(self.nm_manager.is_openvpn_plugin_available())


class OpenVPN3(CFFIStringMixin, ConnectionManager):
    """
    OpenVPN 3 Linux D-Bus backend implementation.
    پیاده‌سازی بک‌اند مدرن OpenVPN 3 بر بستر D-Bus سیستم‌عامل.
    """

    def __init__(self, update_callback):
        super().__init__("OpenVPN3")
        if _libopenvpn3 is None or OVPN3Dbus is None:
            raise RuntimeError(
                "OpenVPN 3 native bindings are unavailable. Install openvpn3-linux "
                "and build with -Dopenvpn3=true."
            ) from _OVPN3_IMPORT_ERROR

        self.ovpn3 = _libopenvpn3.lib
        self.ffi = _libopenvpn3.ffi
        self.callback = update_callback

        self.config_path = None
        self.session_path = None

        self.watch = False
        self.dbus = OVPN3Dbus()

    def get_name(self) -> str:
        return "openvpn3"

    def start_watch(self):
        if not self.watch:
            self.dbus.set_binding(self)
            self.dbus.subscribe_for_attention()
            self.watch = True

    def stop_watch(self):
        """Unsubscribes all OpenVPN 3 D-Bus signals."""
        if self.watch:
            try:
                self.dbus.unsubscribe_all()
            finally:
                self.watch = False

    @classmethod
    def probe_version(cls) -> str | None:
        """
        Reads the OpenVPN 3 version without instantiating the backend.

        خواندن نسخه OpenVPN 3 بدون نمونه‌سازی بک‌اند.
        """
        if _libopenvpn3 is None:
            return None
        return cffi_string(_libopenvpn3.ffi, _libopenvpn3.lib.p_get_version(), True)  # type: ignore[return-value]

    def get_session_path(self):
        return self.session_path

    def is_ready(self) -> bool:
        status = self.to_cffi_string(self.ovpn3.is_ready_to_connect(self.session_path))
        return status is None

    def connect(self, openvpn_config: str):
        """Imports config and prepares an OpenVPN 3 tunnel session."""
        suspicious = audit_ovpn_content(openvpn_config)
        if suspicious:
            message = "Refusing to connect an untrusted profile containing: " + ", ".join(suspicious)
            logger.warning(message)
            if self.callback:
                self.callback(False, message)
            return
        with open(openvpn_config, encoding="utf-8", errors="ignore") as f:
            config_content = f.read()

        ca = self.get_setting(self.SETTING.CA)
        if ca is not None and os.path.exists(ca):
            with open(ca, encoding="utf-8", errors="ignore") as caf:
                config_content += f"\n<ca>\n{caf.read()}\n</ca>\n"

        config_path = self.ovpn3.import_config(
            os.path.basename(openvpn_config).encode("utf-8"),
            config_content.encode("utf-8"),
        )
        self.config_path = self.to_cffi_string(config_path)
        logger.info("OpenVPN 3 Config Path: %s", self.config_path)

        if self.config_path:
            session_path = self.ovpn3.prepare_tunnel(self.config_path)
            self.session_path = self.to_cffi_string(session_path)
            logger.info("OpenVPN 3 Session Path: %s", self.session_path)
            self.status()

    def disconnect(self):
        if self.session_path is not None:
            logger.info("Disconnecting OpenVPN 3 session %s", self.session_path.decode("utf-8"))
            self.ovpn3.disconnect_vpn(self.session_path)
        else:
            # This backend instance owns at most ``session_path``.  A global
            # disconnect could terminate tunnels created by another process.
            logger.warning("OpenVPN 3 disconnect requested without an owned session")
            if self.callback:
                self.callback(False)
        self.session_path = None

    def pause(self):
        self.ovpn3.pause_vpn(self.session_path, b"User Action in eOVPN Pro")

    def resume(self):
        self.ovpn3.resume_vpn(self.session_path)

    def version(self) -> str | None:
        v = self.ovpn3.p_get_version()
        if v:
            return self.to_cffi_string(v, True)
        return None

    def status(self) -> bool:
        return bool(self.ovpn3.p_get_connection_status())
