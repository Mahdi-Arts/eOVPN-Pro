"""
Scoped NetworkManager D-Bus signal listener.
شنونده محدودشده سیگنال‌های D-Bus در NetworkManager.

The listener subscribes to one active-connection object path. Signals emitted
for VPNs created by other applications are never forwarded to the UI.
شنونده فقط به مسیر شیء یک اتصال فعال متصل می‌شود و سیگنال VPNهای متعلق به
برنامه‌های دیگر را به رابط کاربری منتقل نمی‌کند.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import gi

gi.require_version("NM", "1.0")
from gi.repository import Gio, NM

logger = logging.getLogger(__name__)

ERROR_REASONS = (
    "The reason for the VPN connection state change is unknown.",
    "No reason was given for the VPN connection state change.",
    "The VPN connection changed state because the user disconnected it.",
    "The VPN connection changed state because its device was disconnected.",
    "The service providing the VPN connection was stopped.",
    "The IP configuration of the VPN connection was invalid.",
    "The connection attempt to the VPN service timed out.",
    "A timeout occurred while starting the VPN service.",
    "Starting the VPN service failed.",
    "Necessary secrets for the VPN connection were not provided.",
    "Authentication to the VPN server failed.",
    "The connection was deleted from settings.",
)


class NMDbus:
    """Watches one eOVPN-owned active connection / پایش یک اتصال متعلق به eOVPN."""

    def __init__(self) -> None:
        self.connection: Gio.DBusConnection | None = None
        self.subscription_id: int | None = None
        self.object_path: str | None = None

    def watch(self, callback: Callable, object_path: str) -> None:
        """Subscribes to exactly one object path / اشتراک دقیق در یک مسیر شیء."""
        if not object_path or not object_path.startswith("/"):
            raise ValueError("A valid NetworkManager active-connection path is required.")
        self.remove_watch()
        self.connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.object_path = object_path
        self.subscription_id = self.connection.signal_subscribe(
            "org.freedesktop.NetworkManager",
            "org.freedesktop.NetworkManager.VPN.Connection",
            "VpnStateChanged",
            object_path,
            None,
            Gio.DBusSignalFlags.NONE,
            self._on_state_changed,
            callback,
        )
        logger.debug("Watching eOVPN NetworkManager object %s", object_path)

    def remove_watch(self) -> None:
        """Removes the active subscription / حذف اشتراک فعال."""
        if self.connection is not None and self.subscription_id is not None:
            self.connection.signal_unsubscribe(self.subscription_id)
        self.subscription_id = None
        self.object_path = None
        self.connection = None

    def _on_state_changed(
        self,
        _connection,
        _sender_name,
        object_path,
        _interface_name,
        _signal_name,
        parameters,
        update_callback,
    ) -> None:
        """Forwards a validated state transition / ارسال تغییر وضعیت اعتبارسنجی‌شده."""
        if object_path != self.object_path:
            logger.warning("Ignored NetworkManager signal from an unrelated object: %s", object_path)
            return

        status, reason = parameters.unpack()
        if status == NM.VpnConnectionState.ACTIVATED:
            update_callback(True)
            return
        if status in (NM.VpnConnectionState.DISCONNECTED, NM.VpnConnectionState.FAILED):
            reason_message = None
            if status == NM.VpnConnectionState.FAILED and 0 <= reason < len(ERROR_REASONS):
                reason_message = ERROR_REASONS[reason]

            update_callback(False, reason_message)
            return
        update_callback([status, reason])
