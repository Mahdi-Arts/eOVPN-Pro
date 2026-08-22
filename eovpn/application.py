"""
eOVPN-Pro Application Lifecycle & Startup Module
ماژول چرخه حیات و نقطه ورود اجرای برنامه در eOVPN-Pro

Initializes GTK4/Adwaita runtime, command-line arguments, internationalization (i18n),
and Right-to-Left (RTL) layout direction.
راه‌اندازی محیط GTK4/Adwaita، پارامترهای خط فرمان، چندزبانه بودن و تنظیم چیدمان راست‌به‌چپ (RTL).
"""

import logging
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, Gio, GLib, Gtk

from .eovpn_base import Base
from .main_window import MainWindow

logger = logging.getLogger(__name__)


class Eovpn(Base):
    """
    Main application wrapper controlling initialization and UI display.
    کلاس مدیریت اصلی جهت بارگذاری رابط کاربری و تنظیمات زبان.
    """

    def __init__(self, app: Gtk.Application):
        super().__init__()
        self.app = app

    def start(self) -> None:
        """
        Configures text direction (RTL/LTR), custom CSS styles, and initializes MainWindow.
        تنظیم جهت متن (راست‌به‌چپ برای فارسی)، بارگذاری استایل‌های CSS و نمایش پنجره اصلی.
        """
        lang = self.get_setting(self.SETTING.LANGUAGE) or "en"
        if lang == "fa":
            Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
        else:
            Gtk.Widget.set_default_direction(Gtk.TextDirection.LTR)

        css_provider = Gtk.CssProvider()
        try:
            css_provider.load_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/css/main.css")
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
        except Exception as e:
            logger.warning("Failed to load embedded CSS resource: %s", e)

        main_window = MainWindow(self.app)
        main_window.show()


def on_activate(app: Gtk.Application) -> None:
    """Callback when the application is activated / فراخوان هنگام فعال‌سازی برنامه."""
    main = Eovpn(app)
    main.start()


def launch_eovpn() -> int:
    """
    Primary entry point invoked by the executable binary.
    نقطه ورود اصلی فراخوانی‌شده توسط فایل اجرایی برنامه.
    """
    app = Gtk.Application(
        application_id="com.github.mahdi-arts.eovpn-pro", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
    )

    app.add_main_option(
        "debug",
        ord("d"),
        GLib.OptionFlags.NONE,
        GLib.OptionArg.STRING,
        "Show Debug Messages. / نمایش پیام‌های دیباگ.",
        "[CRITICAL|ERROR|WARNING|INFO|DEBUG]",
    )

    # Legacy flags are registered as official (ignored) options instead of
    # being stripped from sys.argv by hand: GLib parsing stays authoritative,
    # old launcher lines keep working, and no argument is silently lost.
    # پرچم‌های قدیمی به‌عنوان گزینه رسمی (نادیده‌گرفته‌شده) ثبت می‌شوند به‌جای
    # حذف دستی از sys.argv؛ پارسر GLib مرجع باقی می‌ماند، خطوط اجرای قدیمی کار
    # می‌کنند و هیچ آرگومانی بی‌صدا از بین نمی‌رود.
    app.add_main_option(
        "config",
        ord("c"),
        GLib.OptionFlags.NONE,
        GLib.OptionArg.STRING,
        "Deprecated legacy option (ignored). / گزینه قدیمی منسوخ (نادیده گرفته می‌شود).",
        None,
    )

    app.connect("activate", on_activate)
    app.connect("command-line", do_command_line)

    return app.run(sys.argv)


def do_command_line(app: Gtk.Application, args: Gio.ApplicationCommandLine) -> bool:
    """
    Handles command-line arguments with GLib option parsing.
    مدیریت آرگومان‌های خط فرمان با پارسر GLib.
    """
    options_dict = args.get_options_dict()

    if options_dict.contains("debug"):
        debug_val = options_dict.lookup_value("debug", None)
        if debug_val:
            debug_lvl = debug_val.get_string()
            if debug_lvl and debug_lvl.isnumeric():
                lvl_int = int(debug_lvl)
                if lvl_int <= 50:
                    logging.basicConfig(
                        level=lvl_int, format="%(levelname)s:%(name)s.py:%(funcName)s:%(message)s"
                    )
            elif debug_lvl in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}:
                logging.basicConfig(
                    level=debug_lvl, format="%(levelname)s:%(name)s.py:%(funcName)s:%(message)s"
                )

    app.activate()
    return True
