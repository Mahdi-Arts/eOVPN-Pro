"""
eOVPN-Pro 2FA / OTP Verification Dialog
پنجره ورود رمز یکبار مصرف دو مرحله‌ای (2FA OTP) در eOVPN-Pro

Supports both per-digit typing and pasting a full 6-digit code into the first
box (the digits are distributed across the boxes automatically).

هم تایپ رقم‌به‌رقم و هم چسباندن کد کامل ۶ رقمی در اولین خانه را پشتیبانی می‌کند
(رقم‌ها به‌صورت خودکار بین خانه‌ها توزیع می‌شوند).
"""

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..eovpn_base import Base, StorageItem

_OTP_LENGTH = 6


class OTPInputWindow(Base):
    """
    Two-Factor Authentication (OTP) entry dialog for static/dynamic challenge.
    پنجره ورود کد احراز هویت دومرحله‌ای برای سناریوهای چالش پویا و ایستا.
    """

    def __init__(self, input_callback: Callable, error_callback: Callable) -> None:
        super().__init__()
        self.callback = input_callback
        self.error_callback = error_callback
        # Guards against re-entrant "changed" signals while pasting.
        # محافظ سیگنال‌های تغییر تو در تو هنگام چسباندن.
        self._distributing = False

        self.builder = Gtk.Builder()
        self.builder.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "otp.ui")

        self.window = self.builder.get_object("OTPMainWindow")
        self.window.connect("close-request", self.manual_close)
        self.window.set_title("2FA OTP Verification")
        self.window.set_default_size(600, 200)
        self.window.set_resizable(False)

        parent = self.retrieve(StorageItem.MAIN_WINDOW)
        if parent and isinstance(parent, Gtk.Window):
            self.window.set_transient_for(parent)
        self.window.set_modal(True)

        self.submit_btn = self.builder.get_object("submit")
        self.submit_btn.set_sensitive(False)
        self.submit_btn.connect("clicked", lambda _: self.return_and_destroy())

        for i in range(1, _OTP_LENGTH + 1):
            entry = self.builder.get_object(f"O{i}")
            entry.set_max_length(1)
            entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
            next_entry = self.builder.get_object(f"O{i + 1}") if i < _OTP_LENGTH else None
            entry.connect("changed", self.on_entry_changed, next_entry)

    def on_entry_changed(self, entry, next_entry):
        """
        Filters to digits, advances focus, and distributes pasted tokens.

        فیلتر ارقام، پیشروی فوکوس و توزیع کد چسبانده‌شده.
        """
        text: str = entry.get_text()
        if not text:
            self._sync_submit_state()
            return False
        if not text.isnumeric():
            entry.set_text("")
            return False

        if len(text) > 1:
            # Paste support: split the token across the digit boxes.
            # پشتیبانی چسباندن: کد چندرقمی بین خانه‌ها پخش می‌شود.
            self._distribute_pasted(text)
            return False

        if len(text) == 1 and next_entry is not None:
            next_entry.grab_focus()

        self._sync_submit_state()
        return False

    def _distribute_pasted(self, token: str) -> None:
        """Fills the digit boxes from a pasted multi-digit token."""
        if self._distributing:
            return
        self._distributing = True
        try:
            digits = [ch for ch in token if ch.isnumeric()][:_OTP_LENGTH]
            last_filled = 0
            for i in range(1, _OTP_LENGTH + 1):
                entry = self.builder.get_object(f"O{i}")
                value = digits[i - 1] if i - 1 < len(digits) else ""
                entry.set_text(value)
                if value:
                    last_filled = i
            if last_filled:
                self.builder.get_object(f"O{last_filled}").grab_focus()
            self._sync_submit_state()
        finally:
            self._distributing = False

    def _sync_submit_state(self) -> None:
        """Enables submit only when all six digits are populated."""
        self.submit_btn.set_sensitive(len(self.gather_otp()) == _OTP_LENGTH)

    def gather_otp(self) -> list[str]:
        otp = []
        for i in range(1, _OTP_LENGTH + 1):
            entry = self.builder.get_object(f"O{i}")
            text = entry.get_text()
            if len(text) == 1:
                otp.append(text)
        return otp

    def return_and_destroy(self):
        self.window.destroy()
        self.callback(self.gather_otp())

    def manual_close(self, window):
        self.error_callback()

    def show(self):
        self.window.set_visible(True)
