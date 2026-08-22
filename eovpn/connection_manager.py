"""
eOVPN-Pro Connection Manager Module
ماژول مدیریت اتصال VPN در eOVPN-Pro

Provides an abstract interface and concrete implementations for connecting,
disconnecting, and monitoring VPN tunnels via NetworkManager and OpenVPN 3 Linux.
ارائه‌دهنده ساختار انتزاعی و پیاده‌سازی‌های عملیاتی جهت مدیریت تونل‌های
OpenVPN از طریق NetworkManager و OpenVPN 3.
"""

import logging
import os
import tempfile
from abc import ABC, abstractmethod

from gi.repository import Secret

from .backend._base import CFFIStringMixin
from .backend.networkmanager import _libeovpn_nm  # type: ignore[attr-defined]
from .backend.networkmanager.dbus import NMDbus
from .eovpn_base import Base

logger = logging.getLogger(__name__)

try:
    from .backend.openvpn3 import _libopenvpn3  # type: ignore[attr-defined]
    from .backend.openvpn3.dbus import OVPN3Dbus
except Exception as e:
    logger.warning("OpenVPN 3 backend module unavailable: %s", e)


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
        return self.__NAME__

    @abstractmethod
    def start_watch(self):
        """Subscribes to connection state change events."""
        pass

    @abstractmethod
    def version(self) -> str | None:
        """Returns backend version string."""
        pass

    @abstractmethod
    def connect(self, openvpn_config: str):
        """Initiates VPN connection using the provided configuration file."""
        pass

    @abstractmethod
    def disconnect(self):
        """Terminates active VPN connection."""
        pass

    @abstractmethod
    def status(self) -> bool:
        """Checks if a VPN tunnel is currently active."""
        pass


class NetworkManager(CFFIStringMixin, ConnectionManager):
    """
    NetworkManager backend implementation using libnm via CFFI and D-Bus signals.
    پیاده‌سازی بک‌اند NetworkManager با استفاده از بایندینگ C و سیگنال‌های D-Bus.
    """

    def __init__(self, callback):
        super().__init__("NetworkManager")
        self.uuid = None
        self.nm_manager = _libeovpn_nm.lib
        self.ffi = _libeovpn_nm.ffi
        self.callback = callback
        self._temp_config_path: str | None = None

        self.dbus = NMDbus()
        self.watch = False

    def get_name(self) -> str:
        return "networkmanager"

    def start_watch(self):
        if not self.watch:
            self.dbus.watch(self.callback)
            self.watch = True

    def stop_watch(self):
        """
        Unsubscribes from NetworkManager D-Bus signals (call on window close).
        لغو اشتراک سیگنال‌های D-Bus شبکه (هنگام بسته‌شدن پنجره فراخوانی شود).
        """
        if self.watch:
            try:
                self.dbus.remove_watch()
            finally:
                self.watch = False

    def connect(self, openvpn_config: str):
        """
        Creates and activates a NetworkManager OpenVPN connection securely.
        ایجاد و فعال‌سازی امن کانکشن در NetworkManager.
        """
        nm_username = self.get_setting(self.SETTING.AUTH_USER)
        nm_password = None
        nm_ca = self.get_setting(self.SETTING.CA)

        # Retrieve password from Secret Service (Keyring) or in-memory session cache
        # دریافت کلمه عبور از سرویس امن Secret Service یا حافظه موقت پروسس
        if nm_username is not None:
            try:
                nm_password = Secret.password_lookup_sync(
                    self.EOVPN_SECRET_SCHEMA,
                    {"username": nm_username},
                    None
                )
            except Exception as e:
                logger.debug("Secret service lookup error: %s", e)
                nm_password = self.get_session_password()

        # Secure Temporary File Creation (0o600 permissions, unique random name)
        # ایجاد امن فایل کانفیگ موقت با مجوز دسترسی اختصاصی کاربر جاری جهت ممانعت از حملات Race Condition
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ovpn", delete=False) as tmp_file:
            os.chmod(tmp_file.name, 0o600)
            self._temp_config_path = tmp_file.name

            with open(openvpn_config, encoding="utf-8", errors="ignore") as f:
                data = f.read() + "\n"

            if nm_ca is not None and os.path.exists(nm_ca):
                with open(nm_ca, encoding="utf-8", errors="ignore") as caf:
                    data += f"\n<ca>\n{caf.read()}\n</ca>\n"

            tmp_file.write(data)

        try:
            uuid = self.nm_manager.add_connection(
                self._temp_config_path.encode("utf-8"),
                (nm_username.encode('utf-8') if nm_username is not None else None),
                (nm_password.encode('utf-8') if nm_password is not None else None),
                self.ffi.NULL,
            )
            self.uuid = self.to_cffi_string(uuid)
            self.nm_manager.activate_connection(self.uuid)

            if self.uuid:
                self.set_setting(self.SETTING.NM_ACTIVE_UUID, self.uuid.decode("utf-8"))
        finally:
            # Securely remove temporary config file after importing into NetworkManager
            # پاک‌سازی امن فایل موقت پس از ایمپورت شدن در سرویس شبکه
            if self._temp_config_path and os.path.exists(self._temp_config_path):
                try:
                    os.remove(self._temp_config_path)
                except Exception as ex:
                    logger.warning("Failed to remove temp config file: %s", ex)
                self._temp_config_path = None

    def disconnect(self):
        """
        Deactivates and removes the VPN connection profile.
        قطع اتصال و حذف پروفایل موقت VPN.
        """
        if self.uuid is None:
            while self.nm_manager.get_active_vpn_connection_uuid() is not None:
                active_uuid = self.to_cffi_string(self.nm_manager.get_active_vpn_connection_uuid())
                if active_uuid:
                    self.nm_manager.disconnect(active_uuid)
                else:
                    break
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
        """
        Unsubscribes from all OpenVPN 3 D-Bus signals (call on window close).
        لغو اشتراک همه سیگنال‌های D-Bus سرویس OpenVPN 3 (هنگام بستن پنجره).
        """
        if self.watch:
            try:
                self.dbus.unsubscribe_all()
            finally:
                self.watch = False

    def get_session_path(self):
        return self.session_path

    def is_ready(self) -> bool:
        status = self.to_cffi_string(self.ovpn3.is_ready_to_connect())
        return status is None

    def connect(self, openvpn_config: str):
        """
        Imports config and prepares tunnel session on OpenVPN 3 Linux service.
        ایمپورت کانفیگ و آماده‌سازی سشن تونل در سرویس OpenVPN 3 لینوکس.
        """
        with open(openvpn_config, encoding="utf-8", errors="ignore") as f:
            config_content = f.read()

        ca = self.get_setting(self.SETTING.CA)
        if ca is not None and os.path.exists(ca):
            with open(ca, encoding="utf-8", errors="ignore") as caf:
                config_content += f"\n<ca>\n{caf.read()}\n</ca>\n"

        config_bytes = config_content.encode('utf-8')
        config_path = self.ovpn3.import_config(
            os.path.basename(openvpn_config).encode('utf-8'),
            config_bytes
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
            logger.info("Disconnecting OpenVPN 3 session %s", self.session_path.decode('utf-8'))
            self.ovpn3.disconnect_vpn()
        else:
            self.ovpn3.disconnect_all_sessions()
            if self.callback:
                self.callback(False)
        self.session_path = None

    def pause(self):
        self.ovpn3.pause_vpn(b"User Action in eOVPN Pro")

    def resume(self):
        self.ovpn3.resume_vpn()

    def version(self) -> str | None:
        v = self.ovpn3.p_get_version()
        if v:
            return self.to_cffi_string(v, True)
        return None

    def status(self) -> bool:
        return bool(self.ovpn3.p_get_connection_status())
