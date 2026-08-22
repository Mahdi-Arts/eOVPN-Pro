"""
GTK-version-compatible destructive action confirmation.
تأیید عملیات مخرب سازگار با نسخه‌های مختلف GTK.

Gtk.AlertDialog is used on GTK 4.10+, with a Gtk.MessageDialog fallback for
supported distributions that still ship GTK 4.6/4.8.
در GTK 4.10 به بالا از Gtk.AlertDialog و در توزیع‌های دارای GTK 4.6/4.8 از
Gtk.MessageDialog به‌عنوان مسیر سازگار استفاده می‌شود.
"""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import Gtk


ConfirmationCallback = Callable[[bool], None]


def confirm_action(
    parent: Gtk.Window,
    *,
    title: str,
    detail: str,
    confirm_label: str,
    cancel_label: str,
    callback: ConfirmationCallback,
) -> None:
    """Presents a modal confirmation and returns one boolean / نمایش تأیید و بازگرداندن نتیجه منطقی."""
    if hasattr(Gtk, "AlertDialog"):
        dialog = Gtk.AlertDialog.new(title)
        dialog.set_detail(detail)
        dialog.set_buttons([cancel_label, confirm_label])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)

        def on_choice(alert, result) -> None:
            try:
                callback(alert.choose_finish(result) == 1)
            except Exception:
                callback(False)

        dialog.choose(parent, None, on_choice)
        return

    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.NONE,
        text=title,
    )
    dialog.set_property("secondary-text", detail)
    dialog.add_button(cancel_label, Gtk.ResponseType.CANCEL)
    confirm_button = dialog.add_button(confirm_label, Gtk.ResponseType.ACCEPT)
    confirm_button.add_css_class("destructive-action")
    dialog.set_default_response(Gtk.ResponseType.CANCEL)

    def on_response(message_dialog, response) -> None:
        message_dialog.destroy()
        callback(response == Gtk.ResponseType.ACCEPT)

    dialog.connect("response", on_response)
    dialog.present()
