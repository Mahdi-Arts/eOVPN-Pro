"""
eOVPN-Pro GTK application lifecycle and command-line entry point.
چرخه عمر برنامه GTK و نقطه ورود خط فرمان eOVPN-Pro.
"""

from __future__ import annotations

import locale
import logging
import sys

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from .constants import APP_ID
from .context import ApplicationContext
from .eovpn_base import Base
from .main_window import MainWindow

logger = logging.getLogger(__name__)


class EOVPNApplicationController(Base):
    """Creates the single main window / ساخت پنجره اصلی تک‌نمونه‌ای."""

    def __init__(
        self,
        app: Gtk.Application,
        context: ApplicationContext,
    ) -> None:
        super().__init__(context)
        self.app = app

    def start(self) -> None:
        """Applies direction, CSS, and presents the main window / اعمال جهت، CSS و نمایش پنجره."""
        language = self.get_setting(self.SETTING.LANGUAGE) or "system"
        system_locale = locale.getlocale()[0] or ""
        is_rtl = language == "fa" or (language == "system" and system_locale.startswith("fa"))
        Gtk.Widget.set_default_direction(
            Gtk.TextDirection.RTL if is_rtl else Gtk.TextDirection.LTR
        )

        provider = Gtk.CssProvider()
        try:
            provider.load_from_resource(self.EOVPN_CSS)
            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
        except Exception as exc:
            logger.warning("Could not load application CSS: %s", exc)

        MainWindow(self.app, self.context).show()


def on_activate(app: Gtk.Application) -> None:
    """Presents the existing window or creates one / نمایش پنجره موجود یا ساخت نمونه جدید."""
    windows = app.get_windows()
    if windows:
        windows[0].present()
        return
    EOVPNApplicationController(app, ApplicationContext()).start()


def _configure_logging(level_name: str) -> None:
    """Enables a validated logging level / فعال‌سازی سطح معتبر لاگ."""
    allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    normalized = level_name.upper()
    if normalized not in allowed:
        logger.warning("Ignored unsupported debug level: %s", level_name)
        return
    logging.basicConfig(
        level=normalized,
        format="%(levelname)s:%(name)s:%(funcName)s:%(message)s",
    )


def do_command_line(
    app: Gtk.Application,
    command_line: Gio.ApplicationCommandLine,
) -> int:
    """Processes supported options and activates the app / پردازش گزینه‌ها و فعال‌سازی برنامه."""
    options = command_line.get_options_dict()
    if options.contains("debug"):
        value = options.lookup_value("debug", None)
        if value:
            _configure_logging(value.get_string())
    app.activate()
    return 0


def launch_eovpn() -> int:
    """Runs the single-instance GTK application / اجرای برنامه تک‌نمونه‌ای GTK."""
    app = Gtk.Application(
        application_id=APP_ID,
        flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
    )
    app.add_main_option(
        "debug",
        ord("d"),
        GLib.OptionFlags.NONE,
        GLib.OptionArg.STRING,
        "Show debug messages.",
        "[CRITICAL|ERROR|WARNING|INFO|DEBUG]",
    )
    app.connect("activate", on_activate)
    app.connect("command-line", do_command_line)
    return app.run(sys.argv)
