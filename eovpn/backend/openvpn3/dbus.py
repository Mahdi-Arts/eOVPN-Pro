"""
eOVPN-Pro OpenVPN 3 D-Bus Event Listener
شنودکننده رویدادها و چالش‌های احراز هویت OpenVPN 3 از طریق D-Bus

This module bridges the openvpn3-linux system service with the GTK UI while
keeping D-Bus subscriptions explicit and disposable. Subscriptions are tracked
so that closing a window or changing backends does not leave stale signal
handlers behind.

این ماژول پل بین سرویس سیستمی openvpn3-linux و رابط GTK است. همه اشتراک‌های
D-Bus به‌صورت صریح نگه‌داری می‌شوند تا هنگام بستن پنجره یا تعویض بک‌اند،
هندلر قدیمی باقی نماند.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from gi.repository import Gio, GLib, Secret

from ...dialogs.otp import OTPInputWindow
from ...eovpn_base import Base

logger = logging.getLogger(__name__)

try:
    from openvpn3 import constants as OVPN3Constants
except Exception as exc:  # pragma: no cover - depends on host openvpn3-linux
    OVPN3Constants = None
    logger.warning("openvpn3 constants unavailable: %s", exc)


class OVPN3Dbus(Base):
    """
    Subscribes to OpenVPN 3 session signals and supplies credentials when needed.
    اشتراک سیگنال‌های نشست OpenVPN 3 و ارائه اعتبارنامه در زمان نیاز.
    """

    def __init__(self):
        super().__init__()
        self.dbus_connection: Any = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.module: Any = None
        self.subscriptions: list[int] = []
        self.attention_subscription: int | None = None

    @staticmethod
    def _constants():
        if OVPN3Constants is None:
            raise RuntimeError("openvpn3 Python constants are unavailable. Install openvpn3-linux.")
        return OVPN3Constants

    def get_auth_password(self) -> str | None:
        """
        Retrieves the authentication password from Keyring or volatile RAM.
        دریافت رمز از Keyring یا حافظه موقت پروسس.
        """
        username = self.get_setting(self.SETTING.AUTH_USER)
        try:
            return Secret.password_lookup_sync(
                self.EOVPN_SECRET_SCHEMA,
                {"username": username} if username else {},
                None,
            )
        except Exception as e:
            logger.debug("Keyring lookup failed, falling back to session memory: %s", e)
            return self.get_session_password()

    def set_binding(self, binding) -> None:
        self.module = binding

    def subscribe_for_attention(self, session_path: str | None = None) -> None:
        """Subscribe to authentication/challenge signals and remember the id."""
        if self.attention_subscription is not None:
            return
        self.attention_subscription = self.dbus_connection.signal_subscribe(
            "net.openvpn.v3.sessions",
            None,
            "AttentionRequired",
            session_path,
            None,
            Gio.DBusSignalFlags.NONE,
            self.sub_attention_signal,
        )
        logger.info(
            "subscribed to AttentionRequired on %s (id = %s)",
            session_path,
            self.attention_subscription,
        )

    def subscribe_for_events(self, callback: Callable, session_path: str | None = None) -> None:
        sid = self.dbus_connection.signal_subscribe(
            "net.openvpn.v3.log",
            "net.openvpn.v3.backends",
            "StatusChange",
            session_path,
            None,
            Gio.DBusSignalFlags.NONE,
            self.sub_status_signal,
            callback,
        )
        self.subscriptions.append(sid)
        logger.info("subscribed to StatusChange on %s (id = %s)", session_path, sid)

    def set_log_forward(self) -> None:
        if not self.module:
            return
        try:
            self.dbus_connection.call_sync(
                "net.openvpn.v3.sessions",
                self.module.get_session_path().decode("utf-8"),
                "net.openvpn.v3.sessions",
                "LogForward",
                GLib.Variant("(b)", (True,)),
                None,
                Gio.DBusSignalFlags.NONE,
                -1,
                None,
            )
        except Exception as exc:
            logger.warning("Failed to enable OpenVPN 3 log forwarding: %s", exc)

    def unsubscribe(self, sub_id: int) -> None:
        logger.info("unsubscribing from signal id: %d", sub_id)
        self.dbus_connection.signal_unsubscribe(sub_id)

    def unsubscribe_all(self) -> None:
        """Unsubscribe both event and attention signal subscriptions."""
        if self.attention_subscription is not None:
            self.unsubscribe(self.attention_subscription)
            self.attention_subscription = None
        for sid in self.subscriptions:
            self.unsubscribe(sid)
        self.subscriptions.clear()

    def send_otp(self, otp: list[str]) -> None:
        constants = self._constants()
        t = constants.ClientAttentionType.CREDENTIALS
        g = constants.ClientAttentionGroup.CHALLENGE_STATIC
        i = 0

        otp_bytes = "".join(str(digit) for digit in otp).encode("utf-8")
        # Never log the OTP value. / مقدار کد یکبارمصرف هرگز لاگ نمی‌شود.
        logger.info("sending OTP for challenge group %s", g)

        self.module.ovpn3.send_auth(
            self.module.get_session_path(),
            t.value,
            g.value,
            i,
            otp_bytes,
        )
        self.try_to_connect()

    def try_to_connect(self) -> None:
        if self.module and self.module.is_ready():
            logger.info("*** connecting to vpn...")
            self.set_log_forward()
            self.subscribe_for_events(
                self.module.callback,
                self.module.get_session_path().decode("utf-8"),
            )
            self.module.ovpn3.connect_vpn(self.module.get_session_path())

    def get_attention(self) -> list[tuple[Any, Any, int, Any]]:
        if not self.module:
            return []

        typegroup = self.dbus_connection.call_sync(
            "net.openvpn.v3.sessions",
            self.module.get_session_path().decode("utf-8"),
            "net.openvpn.v3.sessions",
            "UserInputQueueGetTypeGroup",
            None,
            GLib.VariantType("(a(uu))"),
            Gio.DBusSignalFlags.NONE,
            -1,
            None,
        )

        typegroup_arr = typegroup.get_child_value(0).unpack()
        logger.debug("type-group: %s", typegroup_arr)

        required_attentions = []
        constants = self._constants()

        for atn_type, atn_grp in typegroup_arr:
            params = GLib.Variant("(uu)", (atn_type, atn_grp))
            logger.debug("calling UserInputQueueCheck: %s", params)

            req_inputs = self.dbus_connection.call_sync(
                "net.openvpn.v3.sessions",
                self.module.get_session_path().decode("utf-8"),
                "net.openvpn.v3.sessions",
                "UserInputQueueCheck",
                params,
                GLib.VariantType("(au)"),
                Gio.DBusSignalFlags.NONE,
                -1,
                None,
            )

            req_inputs = req_inputs.get_child_value(0).unpack()
            logger.debug("response from UserInputQueueCheck: %s", req_inputs)

            for _i in req_inputs:
                params = GLib.Variant("(uuu)", (atn_type, atn_grp, _i))
                logger.debug("calling UserInputQueueFetch: %s", params)
                ask = self.dbus_connection.call_sync(
                    "net.openvpn.v3.sessions",
                    self.module.get_session_path().decode("utf-8"),
                    "net.openvpn.v3.sessions",
                    "UserInputQueueFetch",
                    params,
                    GLib.VariantType("(uuussb)"),
                    Gio.DBusSignalFlags.NONE,
                    -1,
                    None,
                )
                ask = ask.get_child_value(3).unpack()
                logger.debug("response from UserInputQueueFetch: %s", ask)
                required_attentions.append(
                    (
                        constants.ClientAttentionType(atn_type),
                        constants.ClientAttentionGroup(atn_grp),
                        _i,
                        ask,
                    )
                )

        return required_attentions

    def sub_attention_signal(
        self,
        connection,
        sender_name,
        object_path,
        interface_name,
        signal_name,
        parameters,
    ) -> None:
        constants = self._constants()
        status = GLib.Variant("(uus)", parameters)
        major = constants.StatusMajor(status.get_child_value(0).get_uint32())
        minor = constants.StatusMinor(status.get_child_value(1).get_uint32())
        reason = status.get_child_value(2).get_string()

        logger.debug(
            "AttentionRequired: %s(%s) %s(%s) %s",
            major,
            status.get_child_value(0).get_uint32(),
            minor,
            status.get_child_value(1).get_uint32(),
            reason,
        )

        attention = self.get_attention()

        for t, g, i, a in attention:
            logger.info("processing required attention: %s %s %i %s", t, g, i, a)
            if a == "username":
                username = self.get_setting(self.SETTING.AUTH_USER) or ""
                self.module.ovpn3.send_auth(
                    self.module.get_session_path(),
                    t.value,
                    g.value,
                    i,
                    username.encode("utf-8"),
                )
            elif a == "password":
                password = self.get_auth_password() or ""
                self.module.ovpn3.send_auth(
                    self.module.get_session_path(),
                    t.value,
                    g.value,
                    i,
                    password.encode("utf-8"),
                )
            elif a == "static_challenge":
                OTPInputWindow(self.send_otp, lambda: self.module.callback(False)).show()
            else:
                logger.error("unknown input required! %s", a)

        self.module.ovpn3.set_dco(
            self.module.get_session_path(),
            self.get_setting(self.SETTING.OPENVPN3_DCO),
        )
        self.try_to_connect()

    def sub_status_signal(
        self,
        connection,
        sender_name,
        object_path,
        interface_name,
        signal_name,
        parameters,
        update_callback,
    ) -> None:
        constants = self._constants()
        status = GLib.Variant("(uus)", parameters)
        major = constants.StatusMajor(status.get_child_value(0).get_uint32())
        minor = constants.StatusMinor(status.get_child_value(1).get_uint32())
        reason = status.get_child_value(2).get_string()
        logger.debug(
            "StatusChange: %s(%s) %s(%s) %s",
            major,
            status.get_child_value(0).get_uint32(),
            minor,
            status.get_child_value(1).get_uint32(),
            reason,
        )

        if major == constants.StatusMajor.CONNECTION and minor == constants.StatusMinor.CONN_AUTH_FAILED:
            logger.error(reason)
            update_callback(False, reason)
            self.unsubscribe_all()
            if self.module:
                self.module.disconnect()
        elif major == constants.StatusMajor.CONNECTION and minor == constants.StatusMinor.CONN_CONNECTING:
            update_callback([])
        elif major == constants.StatusMajor.CONNECTION and minor == constants.StatusMinor.CONN_CONNECTED:
            update_callback(True)
        elif major == constants.StatusMajor.CONNECTION and minor == constants.StatusMinor.CONN_DISCONNECTED:
            self.unsubscribe_all()
            update_callback(False)
        elif major == constants.StatusMajor.CONNECTION and minor == constants.StatusMinor.CONN_PAUSED:
            update_callback(["pause"])
        elif major == constants.StatusMajor.CONNECTION and minor == constants.StatusMinor.CONN_RESUMING:
            update_callback(["resume"])
