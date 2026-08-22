"""
eOVPN-Pro GTK UI Compatibility Helpers
کمک‌های سازگاری رابط کاربری GTK در eOVPN-Pro

Wraps dialogs and file pickers behind a version-tolerant API: the modern
GTK >= 4.10 widgets (``Gtk.AlertDialog``, ``Gtk.FileDialog``) are used when
present, with graceful fallbacks to ``Gtk.MessageDialog`` and
``Gtk.FileChooserNative`` on older GTK4 runtimes (Debian 12, Ubuntu 22.04).

دیالوگ‌ها و انتخاب‌گر فایل را پشت یک API مقاوم به نسخه قرار می‌دهد: ویجت‌های
مدرن GTK 4.10+ وقتی موجود باشند استفاده می‌شوند و در غیر این صورت به ویجت‌های
قدیمی‌تر در رانتایم‌های قدیمی (Debian 12، Ubuntu 22.04) بازمی‌گردد.
"""

from __future__ import annotations

import contextlib
import gettext
import logging
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

logger = logging.getLogger(__name__)

_ = gettext.gettext

ResponseCallback = Callable[[int], None]
PathCallback = Callable[[str], None]


def show_alert(
    parent: Gtk.Window | None,
    title: str,
    detail: str,
    buttons: list[str],
    cancel_index: int | None = None,
    default_index: int | None = None,
    on_response: ResponseCallback | None = None,
) -> None:
    """
    Shows a modal alert and reports the chosen button index (0-based).

    Dismissal (Escape) reports ``cancel_index`` when a modern dialog is used
    and ``-1`` on the legacy fallback.

    یک هشدار مودال نشان می‌دهد و اندیس دکمه انتخاب‌شده (مبنای صفر) را گزارش
    می‌کند؛ رد شدن دیالوگ (Escape) در حالت مدرن ``cancel_index`` و در حالت
    قدیمی ``-1`` گزارش می‌دهد.
    """
    if hasattr(Gtk, "AlertDialog"):
        dialog = Gtk.AlertDialog.new(title)
        dialog.set_detail(detail)
        dialog.set_buttons(list(buttons))
        if cancel_index is not None:
            dialog.set_cancel_button(cancel_index)
        if default_index is not None:
            dialog.set_default_button(default_index)

        def _on_choose(_dialog: Gtk.AlertDialog, result: Gio.AsyncResult) -> None:
            index = cancel_index if cancel_index is not None else -1
            with contextlib.suppress(GLib.Error):
                index = _dialog.choose_finish(result)
            if on_response is not None:
                on_response(index)

        dialog.choose(parent, None, _on_choose, None)
        return

    # Legacy fallback for GTK < 4.10.
    dialog = Gtk.MessageDialog.new()
    if parent is not None:
        dialog.set_transient_for(parent)
    dialog.set_modal(True)
    dialog.set_property("message-type", Gtk.MessageType.QUESTION)
    dialog.set_property("text", title)
    dialog.set_property("secondary-text", detail)
    for index, text in enumerate(buttons):
        dialog.add_button(text, index)
    if default_index is not None:
        dialog.set_default_response(default_index)

    def _on_response(_dialog: Gtk.Dialog, response_id: int) -> None:
        try:
            index = int(response_id)
        except (TypeError, ValueError):
            index = -1
        _dialog.destroy()
        if on_response is not None:
            on_response(index)

    dialog.connect("response", _on_response)
    dialog.show()


def show_critical_error(
    parent: Gtk.Window | None,
    error_messages: list[str],
    on_exit: Callable[[], None],
) -> None:
    """
    Displays a critical modal error dialog whose single button exits the app.

    نمایش دیالوگ خطای بحرانی مودال که تنها دکمه آن برنامه را می‌بندد.
    """
    if hasattr(Gtk, "AlertDialog"):
        dialog = Gtk.AlertDialog.new(_("Error"))
        dialog.set_detail("\n".join(error_messages))
        dialog.set_buttons([_("Exit")])

        def _on_choose(_dialog: Gtk.AlertDialog, result: Gio.AsyncResult) -> None:
            with contextlib.suppress(GLib.Error):
                _dialog.choose_finish(result)
            on_exit()

        dialog.choose(parent, None, _on_choose, None)
        return

    # Legacy fallback for GTK < 4.10.
    dialog = Gtk.MessageDialog.new()
    if parent is not None:
        dialog.set_transient_for(parent)
    dialog.set_modal(True)
    dialog.set_property("message-type", Gtk.MessageType.ERROR)
    dialog.set_property("use-markup", True)
    dialog.set_property("text", "<span weight='bold'>Error</span>")

    box = dialog.get_message_area()
    for message in error_messages:
        box.append(Gtk.Label.new(message))
    exit_btn = dialog.add_button(_("Exit"), 1)
    exit_btn.add_css_class("destructive-action")

    def _on_response(_dialog: Gtk.Dialog, _response_id: int) -> None:
        on_exit()

    dialog.connect("response", _on_response)
    dialog.show()


class FilePicker:
    """
    Version-tolerant file/folder picker for the settings window.

    انتخاب‌گر فایل/پوشه مقاوم به نسخه برای پنجره تنظیمات.
    """

    def __init__(
        self,
        parent: Gtk.Window | None,
        action: Gtk.FileChooserAction,
        title: str,
        filters: list[Gtk.FileFilter] | None = None,
    ) -> None:
        self._parent = parent
        self._title = title
        self._filters: list[Gtk.FileFilter] = list(filters or [])
        self._on_picked: PathCallback | None = None
        self._use_dialog = hasattr(Gtk, "FileDialog")

        if self._use_dialog:
            self._dialog = Gtk.FileDialog.new()
            self._dialog.set_title(title)
            store = Gio.ListStore.new(Gtk.FileFilter)
            for file_filter in self._filters:
                store.append(file_filter)
            self._dialog.set_filters(store)
        else:
            self._native = Gtk.FileChooserNative.new(title=title, action=action)
            self._native.set_transient_for(parent)
            for file_filter in self._filters:
                self._native.add_filter(file_filter)
            self._native.connect("response", self._on_native_response)

    def set_initial_dir(self, path: str | None) -> None:
        """Preselects a folder in both implementations."""
        if not path:
            return
        if self._use_dialog:
            self._dialog.set_initial_folder(Gio.File.new_for_path(path))
        else:
            self._native.set_current_folder(Gio.File.new_for_path(path))

    def connect_picked(self, callback: PathCallback) -> None:
        """Registers the callback receiving the picked path."""
        self._on_picked = callback

    def show(self) -> None:
        """Opens the picker."""
        if self._use_dialog:
            self._dialog.open(self._parent, None, self._on_dialog_result)
        else:
            self._native.show()

    def _emit(self, path: str | None) -> None:
        if path and self._on_picked is not None:
            self._on_picked(path)

    def _on_dialog_result(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = dialog.open_finish(result)
            self._emit(gfile.get_path() if gfile else None)
        except GLib.Error as error:
            logger.debug("File dialog dismissed or failed: %s", error.message)

    def _on_native_response(self, dialog: Gtk.FileChooserNative, response_id: int) -> None:
        if response_id == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            self._emit(gfile.get_path() if gfile else None)


# Re-exported for type annotations in callers.
__all__ = ["FilePicker", "PathCallback", "ResponseCallback", "show_alert", "show_critical_error"]
