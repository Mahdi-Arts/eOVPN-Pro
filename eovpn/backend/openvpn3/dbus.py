"""
Scoped OpenVPN 3 D-Bus authentication and status controller.
کنترلر محدودشده احراز هویت و وضعیت D-Bus در OpenVPN 3.

Subscriptions always target the one session object created by eOVPN. Secret
values are submitted to D-Bus but never included in application logs.
اشتراک‌ها همیشه به همان نشست ساخته‌شده توسط eOVPN محدودند. مقادیر محرمانه به
D-Bus ارسال می‌شوند، اما هرگز در لاگ برنامه قرار نمی‌گیرند.
"""

from __future__ import annotations

import gettext
import logging
from collections.abc import Callable

from gi.repository import Gio, GLib

from eovpn.constants import DBUS_TIMEOUT_MS
from eovpn.context import ApplicationContext
from eovpn.dialogs.otp import OTPInputWindow
from eovpn.eovpn_base import Base
from eovpn.secret_store import DEFAULT_SECRET_STORE

logger = logging.getLogger(__name__)
_ = gettext.gettext

try:
    from openvpn3 import constants as OVPN3Constants
except Exception as exc:  # pragma: no cover - depends on optional system package
    OVPN3Constants = None
    logger.warning("OpenVPN 3 Python constants are unavailable: %s", exc)


class OVPN3Dbus(Base):
    """Owns D-Bus subscriptions for one OpenVPN 3 session / مالک اشتراک‌های یک نشست."""

    def __init__(self, context: ApplicationContext | None = None) -> None:
        super().__init__(context)
        if OVPN3Constants is None:
            raise RuntimeError(_("OpenVPN 3 Python constants are unavailable."))
        self.connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.module = None
        self.subscriptions: list[int] = []
        self.session_path: str | None = None
        self.update_callback: Callable | None = None

    def set_binding(self, binding) -> None:
        self.module = binding

    def subscribe(self, session_path: str, callback: Callable | None) -> None:
        """Subscribes attention and status to one exact path / اشتراک توجه و وضعیت در یک مسیر دقیق."""
        if not session_path or not session_path.startswith("/"):
            raise ValueError("A valid OpenVPN 3 session path is required.")
        self.unsubscribe_all()
        self.session_path = session_path
        self.update_callback = callback
        self.subscriptions.append(
            self.connection.signal_subscribe(
                "net.openvpn.v3.sessions",
                None,
                "AttentionRequired",
                session_path,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_attention,
            )
        )
        self.subscriptions.append(
            self.connection.signal_subscribe(
                "net.openvpn.v3.log",
                "net.openvpn.v3.backends",
                "StatusChange",
                session_path,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_status,
            )
        )
        logger.debug("Subscribed to owned OpenVPN 3 session %s", session_path)

    def unsubscribe_all(self) -> None:
        """Removes every owned subscription / حذف همه اشتراک‌های متعلق به این نمونه."""
        for subscription_id in self.subscriptions:
            self.connection.signal_unsubscribe(subscription_id)
        self.subscriptions.clear()
        self.session_path = None

    def _call(self, interface: str, method: str, parameters, reply_type=None):
        """Performs one finite D-Bus call / اجرای یک فراخوانی D-Bus با زمان محدود."""
        if not self.session_path:
            raise RuntimeError(_("OpenVPN 3 session is not initialized."))
        return self.connection.call_sync(
            "net.openvpn.v3.sessions",
            self.session_path,
            interface,
            method,
            parameters,
            reply_type,
            Gio.DBusCallFlags.NONE,
            DBUS_TIMEOUT_MS,
            None,
        )

    def _enable_log_forwarding(self) -> None:
        self._call(
            "net.openvpn.v3.sessions",
            "LogForward",
            GLib.Variant("(b)", (True,)),
        )

    def try_to_connect(self) -> None:
        """Connects when Ready reports no pending input / اتصال پس از تکمیل ورودی‌های لازم."""
        if self.module is None:
            return
        if not self.module.is_ready():
            return
        try:
            self._enable_log_forwarding()
            if not self.module.native.connect_vpn():
                raise RuntimeError(_("OpenVPN 3 rejected the Connect request."))
        except Exception as exc:
            logger.error("OpenVPN 3 connect request failed: %s", exc)
            if self.update_callback:
                self.update_callback(False, str(exc))

    def _required_inputs(self) -> list[tuple[object, object, int, str, str]]:
        """Fetches pending credential prompts / دریافت درخواست‌های احراز هویت در انتظار."""
        response = self._call(
            "net.openvpn.v3.sessions",
            "UserInputQueueGetTypeGroup",
            None,
            GLib.VariantType("(a(uu))"),
        )
        type_groups = response.unpack()[0]
        required: list[tuple[object, object, int, str, str]] = []

        for attention_type, attention_group in type_groups:
            indexes = self._call(
                "net.openvpn.v3.sessions",
                "UserInputQueueCheck",
                GLib.Variant("(uu)", (attention_type, attention_group)),
                GLib.VariantType("(au)"),
            ).unpack()[0]
            for index in indexes:
                fetched = self._call(
                    "net.openvpn.v3.sessions",
                    "UserInputQueueFetch",
                    GLib.Variant("(uuu)", (attention_type, attention_group, index)),
                    GLib.VariantType("(uuussb)"),
                ).unpack()
                _type, _group, _index, variable_name, description, _hidden = fetched
                required.append(
                    (
                        OVPN3Constants.ClientAttentionType(attention_type),
                        OVPN3Constants.ClientAttentionGroup(attention_group),
                        index,
                        variable_name,
                        description,
                    )
                )
        return required

    def _submit(self, attention_type, attention_group, index: int, value: str) -> bool:
        """Submits a secret without logging it / ارسال مقدار محرمانه بدون ثبت در لاگ."""
        if self.module is None or not self.module.get_session_path():
            return False
        return bool(
            self.module.native.send_auth(
                self.module.get_session_path(),
                attention_type.value,
                attention_group.value,
                index,
                value.encode("utf-8"),
            )
        )

    def _submit_challenge(
        self,
        value: str,
        attention_type,
        attention_group,
        index: int,
    ) -> None:
        if not self._submit(attention_type, attention_group, index, value):
            if self.update_callback:
                self.update_callback(False, _("OpenVPN 3 rejected the challenge response."))
            return
        self.try_to_connect()

    def _on_attention(
        self,
        _connection,
        _sender_name,
        object_path,
        _interface_name,
        _signal_name,
        _parameters,
    ) -> None:
        """Handles only attention from the owned path / پردازش توجه فقط از مسیر متعلق به برنامه."""
        if object_path != self.session_path:
            logger.warning("Ignored OpenVPN 3 attention from unrelated path %s", object_path)
            return
        try:
            requests = self._required_inputs()
            username = self.get_setting(self.SETTING.AUTH_USER) or ""
            password = DEFAULT_SECRET_STORE.lookup(username) or ""
            for attention_type, attention_group, index, variable, description in requests:
                if variable == "username":
                    if not self._submit(attention_type, attention_group, index, username):
                        raise RuntimeError(_("OpenVPN 3 rejected the username."))
                elif variable == "password":
                    if not self._submit(attention_type, attention_group, index, password):
                        raise RuntimeError(_("OpenVPN 3 rejected the password."))
                elif variable in ("static_challenge", "dynamic_challenge"):
                    OTPInputWindow(
                        lambda value, t=attention_type, g=attention_group, i=index: self._submit_challenge(
                            value, t, g, i
                        ),
                        lambda: self.update_callback and self.update_callback(
                            False, _("Authentication challenge was cancelled.")
                        ),
                        prompt=description,
                        context=self.context,
                    ).show()
                    return
                else:
                    raise RuntimeError(
                        _("Unsupported OpenVPN 3 credential prompt: {}").format(
                            variable
                        )
                    )
            self.try_to_connect()
        except Exception as exc:
            logger.error("OpenVPN 3 authentication flow failed: %s", exc)
            if self.update_callback:
                self.update_callback(False, str(exc))

    def _on_status(
        self,
        _connection,
        _sender_name,
        object_path,
        _interface_name,
        _signal_name,
        parameters,
    ) -> None:
        """Maps an owned status signal to the common callback / نگاشت وضعیت نشست به Callback مشترک."""
        if object_path != self.session_path:
            logger.warning("Ignored OpenVPN 3 status from unrelated path %s", object_path)
            return

        major_value, minor_value, reason = parameters.unpack()
        major = OVPN3Constants.StatusMajor(major_value)
        minor = OVPN3Constants.StatusMinor(minor_value)
        callback = self.update_callback
        if callback is None:
            return

        if (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_AUTH_FAILED
        ):
            callback(False, reason)
            self.unsubscribe_all()
            self.module.native.disconnect_vpn()
            self.module.handle_backend_disconnected()
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_CONNECTING
        ):
            callback([])
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_CONNECTED
        ):
            callback(True)
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_DISCONNECTED
        ):
            callback(False)
            self.module.handle_backend_disconnected()
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_PAUSED
        ):
            callback(["pause"])
        elif (
            major == OVPN3Constants.StatusMajor.CONNECTION
            and minor == OVPN3Constants.StatusMinor.CONN_RESUMING
        ):
            callback(["resume"])
