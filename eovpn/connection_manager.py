"""
Scoped VPN backend implementations for eOVPN-Pro.
پیاده‌سازی محدودشده بک‌اندهای VPN در eOVPN-Pro.

Both backends operate only on UUIDs or D-Bus object paths created by this
application. They never disconnect, delete, or monitor unrelated VPN sessions.
هر دو بک‌اند فقط روی UUID یا مسیر D-Bus ساخته‌شده توسط همین برنامه عمل می‌کنند
و نشست‌های VPN نامرتبط را پایش، قطع یا حذف نمی‌کنند.
"""

from __future__ import annotations

import gettext
import logging
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from gi.repository import NM

from .backend.networkmanager.dbus import NMDbus
from .constants import NM_PROFILE_LABEL_PREFIX
from .context import ApplicationContext
from .eovpn_base import Base
from .secret_store import DEFAULT_SECRET_STORE

logger = logging.getLogger(__name__)
_ = gettext.gettext


class BackendUnavailableError(RuntimeError):
    """Raised when an optional system backend is unavailable / خطای نبود بک‌اند اختیاری."""


class ConnectionError(RuntimeError):
    """Raised when a backend operation fails / خطای شکست عملیات بک‌اند."""


class ConnectionManager(ABC, Base):
    """Minimal backend contract / قرارداد حداقلی بک‌اند اتصال."""

    def __init__(
        self,
        name: str,
        context: ApplicationContext | None = None,
    ) -> None:
        super().__init__(context)
        self._name = name

    @abstractmethod
    def get_name(self) -> str:
        """Returns the stable backend identifier / بازگرداندن شناسه پایدار بک‌اند."""

    @abstractmethod
    def start_watch(self) -> None:
        """Requests scoped status monitoring / درخواست پایش محدود وضعیت."""

    @abstractmethod
    def stop_watch(self) -> None:
        """Stops status monitoring / توقف پایش وضعیت."""

    @abstractmethod
    def version(self) -> str | None:
        """Returns backend version / بازگرداندن نسخه بک‌اند."""

    @abstractmethod
    def connect(self, openvpn_config: str) -> bool:
        """Starts one owned VPN session / شروع یک نشست متعلق به برنامه."""

    @abstractmethod
    def disconnect(self) -> bool:
        """Stops only the owned session / قطع فقط نشست متعلق به برنامه."""

    @abstractmethod
    def status(self) -> bool:
        """Reports only the owned session state / گزارش فقط وضعیت نشست خود برنامه."""


class NetworkManager(ConnectionManager):
    """
    NetworkManager backend with UUID-scoped lifecycle and D-Bus monitoring.
    بک‌اند NetworkManager با چرخه عمر و پایش محدود به UUID.
    """

    def __init__(
        self,
        callback,
        native_module=None,
        dbus: NMDbus | None = None,
        context: ApplicationContext | None = None,
    ) -> None:
        super().__init__("NetworkManager", context)
        if native_module is None:
            try:
                from .backend.networkmanager import _libeovpn_nm as native_module
            except Exception as exc:
                raise BackendUnavailableError(
                    _("The NetworkManager native binding is unavailable.")
                ) from exc

        self.native = native_module.lib
        self.ffi = native_module.ffi
        self.callback = callback
        self.dbus = dbus or NMDbus()
        self.uuid: str | None = self.get_setting(self.SETTING.NM_ACTIVE_UUID)
        self._watch_requested = False
        self._disconnect_event_seen = False
        self._temp_config_path: str | None = None

        # A saved UUID is trusted only because eOVPN created and persisted it.
        # UUID ذخیره‌شده فقط به‌دلیل ایجاد و ثبت توسط eOVPN قابل اعتماد است.
        if self.uuid and self.uuid not in self._owned_uuids():
            self.uuid = None
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, None)

    def get_name(self) -> str:
        return "networkmanager"

    def _consume_c_string(self, value, decode: bool = True):
        """Copies and frees an owned C string / کپی و آزادسازی رشته تحت مالکیت C."""
        if value == self.ffi.NULL:
            return None
        raw = self.ffi.string(value)
        self.native.eovpn_free(value)
        return raw.decode("utf-8", errors="replace") if decode else raw

    def _owned_uuids(self) -> set[str]:
        return set(self.get_setting(self.SETTING.NM_OWNED_UUIDS) or [])

    def _remember_uuid(self, uuid: str) -> None:
        owned = self._owned_uuids()
        owned.add(uuid)
        self.set_setting(self.SETTING.NM_OWNED_UUIDS, sorted(owned))
        self.set_setting(self.SETTING.NM_ACTIVE_UUID, uuid)

    def _forget_uuid(self, uuid: str) -> None:
        owned = self._owned_uuids()
        owned.discard(uuid)
        self.set_setting(self.SETTING.NM_OWNED_UUIDS, sorted(owned))
        if self.get_setting(self.SETTING.NM_ACTIVE_UUID) == uuid:
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, None)

    def _active_object_path(self) -> str | None:
        if not self.uuid:
            return None
        value = self.native.get_active_vpn_connection_path(self.uuid.encode("utf-8"))
        return self._consume_c_string(value)

    def _on_dbus_event(self, result, error=None) -> None:
        if result is False:
            self._disconnect_event_seen = True
        if self.callback:
            self.callback(result, error)

    def _attach_watch(self) -> None:
        if not self._watch_requested:
            return
        object_path = self._active_object_path()
        if object_path:
            self.dbus.watch(self._on_dbus_event, object_path)

    def start_watch(self) -> None:
        self._watch_requested = True
        self._attach_watch()

    def stop_watch(self) -> None:
        self._watch_requested = False
        self.dbus.remove_watch()

    def _validate_config(self, openvpn_config: str) -> Path:
        root = Path(self.EOVPN_OVPN_CONFIG_DIR).resolve()
        candidate = Path(openvpn_config)
        if candidate.is_symlink():
            raise ConnectionError(_("Selected OpenVPN configuration must not be a symbolic link."))
        config = candidate.resolve()
        try:
            config.relative_to(root)
        except ValueError as exc:
            raise ConnectionError(_("Configuration path is outside the managed repository.")) from exc
        if not config.is_file() or config.suffix.lower() != ".ovpn":
            raise ConnectionError(_("Selected OpenVPN configuration is not a safe regular file."))
        config.chmod(0o600)
        return config

    def _remove_stale_profile(self) -> None:
        if not self.uuid or self.status():
            return
        stale = self.uuid
        if self.native.delete_connection(stale.encode("utf-8")):
            self._forget_uuid(stale)
            self.uuid = None

    def connect(self, openvpn_config: str) -> bool:
        """Imports, activates, and watches one eOVPN-owned NM profile."""
        config = self._validate_config(openvpn_config)
        self._remove_stale_profile()
        if self.uuid and self.status():
            raise ConnectionError(_("An eOVPN NetworkManager connection is already active."))
        if not self.is_openvpn_plugin_available():
            raise BackendUnavailableError(
                _("The NetworkManager OpenVPN editor plugin is not installed.")
            )

        username = self.get_setting(self.SETTING.AUTH_USER)
        password = DEFAULT_SECRET_STORE.lookup(username)
        ca_path = self.get_setting(self.SETTING.CA)

        data = config.read_text(encoding="utf-8", errors="ignore") + "\n"
        has_ca_directive = any(
            line.strip().lower().startswith(("ca ", "<ca>"))
            for line in data.splitlines()
            if line.strip() and not line.lstrip().startswith(("#", ";"))
        )
        if not has_ca_directive and ca_path and Path(ca_path).is_file():
            ca_data = Path(ca_path).read_text(encoding="utf-8", errors="ignore")
            data += f"\n<ca>\n{ca_data}\n</ca>\n"

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".ovpn",
                prefix="eovpn-",
                delete=False,
            ) as temporary:
                self._temp_config_path = temporary.name
                os.chmod(temporary.name, 0o600)
                temporary.write(data)
                temporary.flush()
                os.fsync(temporary.fileno())

            profile_name = f"{NM_PROFILE_LABEL_PREFIX} — {config.stem}"
            raw_uuid = self.native.add_connection(
                self._temp_config_path.encode("utf-8"),
                profile_name.encode("utf-8"),
                username.encode("utf-8") if username else self.ffi.NULL,
                password.encode("utf-8") if password else self.ffi.NULL,
                self.ffi.NULL,
            )
            uuid = self._consume_c_string(raw_uuid)
            if not uuid:
                raise ConnectionError(_("NetworkManager could not import the configuration."))

            self.uuid = uuid
            self._remember_uuid(uuid)
            if not self.native.activate_connection(uuid.encode("utf-8")):
                self.native.delete_connection(uuid.encode("utf-8"))
                self._forget_uuid(uuid)
                self.uuid = None
                raise ConnectionError(_("NetworkManager could not activate the VPN profile."))

            self._attach_watch()
            if self.status() and self.callback:
                self.callback(True)
            return True
        finally:
            if self._temp_config_path:
                try:
                    Path(self._temp_config_path).unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Could not remove private temporary configuration: %s", exc)
                self._temp_config_path = None

    def disconnect(self) -> bool:
        """Deactivates and removes only the current eOVPN profile."""
        if not self.uuid:
            return False

        uuid = self.uuid
        was_active = self.status()
        self._disconnect_event_seen = False
        disconnected = True
        if was_active:
            disconnected = bool(self.native.disconnect(uuid.encode("utf-8")))
        deleted = bool(self.native.delete_connection(uuid.encode("utf-8")))
        if deleted:
            self._forget_uuid(uuid)
            self.uuid = None
        self.stop_watch()
        if self.callback and not self._disconnect_event_seen:
            self.callback(False, None if disconnected else _("NetworkManager disconnect failed."))
        return disconnected and deleted

    def status(self) -> bool:
        if not self.uuid:
            return False
        state = self.native.is_vpn_activated(self.uuid.encode("utf-8"))
        return state == int(NM.VpnConnectionState.ACTIVATED)

    def delete_managed_connections(self) -> tuple[int, int]:
        """
        Deletes only UUIDs recorded as eOVPN-owned.
        حذف فقط UUIDهایی که مالکیت آن‌ها توسط eOVPN ثبت شده است.
        """
        deleted = 0
        failed: set[str] = set()
        active_uuid = self.uuid
        for uuid in sorted(self._owned_uuids()):
            encoded = uuid.encode("utf-8")
            state = self.native.is_vpn_activated(encoded)
            if state != -1 and not self.native.disconnect(encoded):
                failed.add(uuid)
                continue
            if self.native.delete_connection(encoded):
                deleted += 1
            else:
                failed.add(uuid)
        self.set_setting(self.SETTING.NM_OWNED_UUIDS, sorted(failed))
        if active_uuid not in failed:
            self.uuid = None
            self.set_setting(self.SETTING.NM_ACTIVE_UUID, None)
        return deleted, len(failed)

    def version(self) -> str | None:
        return self._consume_c_string(self.native.get_version())

    def is_openvpn_plugin_available(self) -> bool:
        return bool(self.native.is_openvpn_plugin_available())


class OpenVPN3(ConnectionManager):
    """OpenVPN 3 backend scoped to one persisted session path."""

    def __init__(
        self,
        callback,
        native_module=None,
        dbus=None,
        context: ApplicationContext | None = None,
    ) -> None:
        super().__init__("OpenVPN3", context)
        if native_module is None:
            try:
                from .backend.openvpn3 import _libopenvpn3 as native_module
            except Exception as exc:
                raise BackendUnavailableError(_("The OpenVPN 3 backend is unavailable.")) from exc
        if dbus is None:
            try:
                from .backend.openvpn3.dbus import OVPN3Dbus

                dbus = OVPN3Dbus(context=self.context)
            except Exception as exc:
                raise BackendUnavailableError(_("OpenVPN 3 D-Bus is unavailable.")) from exc

        self.native = native_module.lib
        self.ffi = native_module.ffi
        self.callback = callback
        self.dbus = dbus
        self.config_path: str | None = self.get_setting(self.SETTING.OVPN3_CONFIG_PATH)
        self.session_path: str | None = self.get_setting(self.SETTING.OVPN3_SESSION_PATH)
        self._watch_requested = False
        self.dbus.set_binding(self)

        if self.session_path:
            self.native.init_unique_session(self.session_path.encode("utf-8"))

    def get_name(self) -> str:
        return "openvpn3"

    def _consume_c_string(self, value) -> str | None:
        if value == self.ffi.NULL:
            return None
        raw = self.ffi.string(value).decode("utf-8", errors="replace")
        self.native.eovpn_free(value)
        return raw

    def start_watch(self) -> None:
        self._watch_requested = True
        if self.session_path:
            self.dbus.subscribe(self.session_path, self.callback)

    def stop_watch(self) -> None:
        self._watch_requested = False
        self.dbus.unsubscribe_all()

    def get_session_path(self) -> bytes | None:
        return self.session_path.encode("utf-8") if self.session_path else None

    def is_ready(self) -> bool:
        error = self._consume_c_string(self.native.is_ready_to_connect())
        return error is None

    def connect(self, openvpn_config: str) -> bool:
        candidate = Path(openvpn_config)
        if candidate.is_symlink():
            raise ConnectionError(_("Selected OpenVPN configuration must not be a symbolic link."))
        config = candidate.resolve()
        root = Path(self.EOVPN_OVPN_CONFIG_DIR).resolve()
        try:
            config.relative_to(root)
        except ValueError as exc:
            raise ConnectionError(_("Configuration path is outside the managed repository.")) from exc
        if not config.is_file() or config.suffix.lower() != ".ovpn":
            raise ConnectionError(_("Selected OpenVPN configuration is not a safe regular file."))
        if self.session_path:
            self.disconnect()

        content = config.read_text(encoding="utf-8", errors="ignore")
        ca_path = self.get_setting(self.SETTING.CA)
        has_ca_directive = any(
            line.strip().lower().startswith(("ca ", "<ca>"))
            for line in content.splitlines()
            if line.strip() and not line.lstrip().startswith(("#", ";"))
        )
        if not has_ca_directive and ca_path and Path(ca_path).is_file():
            ca_data = Path(ca_path).read_text(encoding="utf-8", errors="ignore")
            content += f"\n<ca>\n{ca_data}\n</ca>\n"

        raw_config_path = self.native.import_config(
            config.name.encode("utf-8"), content.encode("utf-8")
        )
        self.config_path = self._consume_c_string(raw_config_path)
        if not self.config_path:
            raise ConnectionError(_("OpenVPN 3 could not import the configuration."))
        self.set_setting(self.SETTING.OVPN3_CONFIG_PATH, self.config_path)

        raw_session_path = self.native.prepare_tunnel(self.config_path.encode("utf-8"))
        self.session_path = self._consume_c_string(raw_session_path)
        if not self.session_path:
            self.set_setting(self.SETTING.OVPN3_CONFIG_PATH, None)
            self.config_path = None
            raise ConnectionError(_("OpenVPN 3 could not create a tunnel session."))
        self.set_setting(self.SETTING.OVPN3_SESSION_PATH, self.session_path)

        session_bytes = self.session_path.encode("utf-8")
        self.native.init_unique_session(session_bytes)
        self.native.set_dco(
            session_bytes,
            int(bool(self.get_setting(self.SETTING.OPENVPN3_DCO))),
        )
        self.dbus.subscribe(self.session_path, self.callback)
        self._watch_requested = True
        self.dbus.try_to_connect()
        return True

    def _clear_owned_session(self) -> None:
        """Clears only the persisted paths owned by this instance / پاک‌سازی مسیرهای متعلق به همین نمونه."""
        self.stop_watch()
        self.session_path = None
        self.config_path = None
        self.set_setting(self.SETTING.OVPN3_SESSION_PATH, None)
        self.set_setting(self.SETTING.OVPN3_CONFIG_PATH, None)

    def handle_backend_disconnected(self) -> None:
        """Accepts a terminal event already reported by D-Bus / ثبت رویداد نهایی گزارش‌شده توسط D-Bus."""
        self._clear_owned_session()

    def disconnect(self) -> bool:
        if not self.session_path:
            return False
        # Unsubscribe first so one user action produces one UI transition.
        # ابتدا اشتراک حذف می‌شود تا هر اقدام کاربر فقط یک تغییر UI ایجاد کند.
        self.stop_watch()
        success = bool(self.native.disconnect_vpn())
        self._clear_owned_session()
        if self.callback:
            self.callback(False, None if success else _("OpenVPN 3 disconnect failed."))
        return success

    def pause(self) -> bool:
        return bool(self.native.pause_vpn(b"User action in eOVPN Pro"))

    def resume(self) -> bool:
        return bool(self.native.resume_vpn())

    def version(self) -> str | None:
        return self._consume_c_string(self.native.p_get_version())

    def status(self) -> bool:
        if not self.session_path:
            return False
        return bool(
            self.native.get_specific_connection_status(
                self.session_path.encode("utf-8")
            )
        )
