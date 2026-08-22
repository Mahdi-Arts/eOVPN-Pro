"""
eOVPN-Pro NetworkManager D-Bus Listener
شنودکننده رویدادهای وضعیت اتصالات NetworkManager از طریق D-Bus در eOVPN-Pro
"""

import gi

gi.require_version("NM", "1.0")
import logging

from gi.repository import NM, Gio, GLib

logger = logging.getLogger(__name__)

error_reasons = [
    "The reason for the VPN connection state change is unknown.",
    "No reason was given for the VPN connection state change.",
    "The VPN connection changed state because the user disconnected it.",
    "The VPN connection changed state because the device it was using was disconnected.",
    "The service providing the VPN connection was stopped.",
    "The IP config of the VPN connection was invalid.",
    "The connection attempt to the VPN service timed out.",
    "A timeout occurred while starting the service providing the VPN connection.",
    "Starting the service providing the VPN connection failed.",
    "Necessary secrets for the VPN connection were not provided.",
    "Authentication to the VPN server failed.",
    "The connection was deleted from settings."
]


class NMDbus:
    """
    Subscribes to NetworkManager VPN connection state signals over System D-Bus.
    اشتراک در سیگنال‌های تغییر وضعیت VPN در سرویس NetworkManager.
    """

    def __init__(self):
        self.conn = None
        self.conn_id = None

    def watch(self, callback):
        self.conn = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        logger.debug("NetworkManager D-Bus connection: %s", self.conn)

        self.conn_id = self.conn.signal_subscribe(
            "org.freedesktop.NetworkManager",
            "org.freedesktop.NetworkManager.VPN.Connection",
            "VpnStateChanged",
            None,
            None,
            Gio.DBusSignalFlags.NONE,
            self.sub_callback,
            callback
        )

    def remove_watch(self):
        if self.conn and self.conn_id:
            self.conn.signal_unsubscribe(self.conn_id)
            self.conn_id = None

    def sub_callback(
        self, connection, sender_name, object_path, interface_name,
        signal_name, parameters, update_callback,
    ):
        logger.debug("NM Signal: %s %s", signal_name, parameters)

        x = GLib.Variant("(uu)", parameters)
        status = x.get_child_value(0).get_uint32()
        reason = x.get_child_value(1).get_uint32()

        if status == NM.VpnConnectionState.ACTIVATED:
            logger.debug("NetworkManager VPN connected.")
            update_callback(True)
        elif status in (NM.VpnConnectionState.DISCONNECTED, NM.VpnConnectionState.FAILED):
            logger.debug("NetworkManager VPN disconnected (reason: %d).", reason)
            is_connection_deletion_required = reason in [5, 6, 7, 8, 9, 10]
            reason_msg = None
            if is_connection_deletion_required and reason < len(error_reasons):
                reason_msg = error_reasons[reason]
            GLib.timeout_add_seconds(1, update_callback, False, reason_msg)
        else:
            update_callback([status, reason])
