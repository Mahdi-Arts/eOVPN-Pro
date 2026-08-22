"""
OpenVPN authentication challenge dialog.
پنجره پاسخ به چالش احراز هویت OpenVPN.

A single secure entry supports both common numeric TOTPs and provider-specific
static challenge responses. The value is cleared before the window is closed.
یک ورودی امن هم کدهای عددی TOTP و هم پاسخ‌های ایستای سرویس‌دهنده را پشتیبانی
می‌کند و مقدار آن پیش از بستن پنجره پاک می‌شود.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from eovpn.context import ApplicationContext
from eovpn.eovpn_base import Base, StorageItem


class OTPInputWindow(Base):
    """Modal authentication challenge window / پنجره مودال چالش احراز هویت."""

    def __init__(
        self,
        input_callback: Callable[[str], None],
        error_callback: Callable[[], None],
        *,
        prompt: str | None = None,
        context: ApplicationContext | None = None,
    ) -> None:
        super().__init__(context)
        self.input_callback = input_callback
        self.error_callback = error_callback
        self._completed = False

        self.builder = Gtk.Builder()
        self.builder.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/otp.ui")
        self.window = self.builder.get_object("otp_window")
        self.entry: Gtk.PasswordEntry = self.builder.get_object("otp_entry")
        self.submit_button: Gtk.Button = self.builder.get_object("submit")
        prompt_label: Gtk.Label = self.builder.get_object("prompt_label")

        parent = self.retrieve(StorageItem.MAIN_WINDOW)
        if isinstance(parent, Gtk.Window):
            self.window.set_transient_for(parent)
        if prompt:
            prompt_label.set_text(prompt)

        self.window.connect("close-request", self._on_close)
        self.entry.connect("changed", self._on_changed)
        self.entry.connect("activate", lambda *_: self._submit())
        self.submit_button.connect("clicked", lambda *_: self._submit())

    def _on_changed(self, entry: Gtk.PasswordEntry) -> None:
        """Enables Verify for a non-empty response / فعال‌سازی تأیید برای پاسخ غیرخالی."""
        self.submit_button.set_sensitive(bool(entry.get_text().strip()))

    def _submit(self) -> None:
        """Copies, clears, closes, then submits / کپی، پاک‌سازی، بستن و سپس ارسال پاسخ."""
        if self._completed:
            return
        value = self.entry.get_text().strip()
        if not value:
            return
        self._completed = True
        self.entry.set_text("")
        self.window.destroy()
        self.input_callback(value)

    def _on_close(self, _window: Gtk.Window) -> bool:
        """Reports cancellation once / گزارش یک‌باره لغو چالش."""
        if not self._completed:
            self._completed = True
            self.entry.set_text("")
            self.error_callback()
        return False

    def show(self) -> None:
        """Presents and focuses the secure entry / نمایش پنجره و تمرکز روی ورودی امن."""
        self.window.present()
        self.entry.grab_focus()
