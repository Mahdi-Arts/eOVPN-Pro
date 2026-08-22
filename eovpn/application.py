"""
eOVPN-Pro Application Lifecycle & Startup Module
ماژول چرخه حیات و نقطه ورود اجرای برنامه در eOVPN-Pro

Initializes GTK4/Adwaita runtime, command-line arguments, internationalization (i18n),
and Right-to-Left (RTL) layout direction.
راه‌اندازی محیط GTK4/Adwaita، پارامترهای خط فرمان، چندزبانه بودن و تنظیم چیدمان راست‌به‌چپ (RTL).
"""

import sys
import logging

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Gio, Gdk

from .eovpn_base import Base
from .main_window import MainWindow

logger = logging.getLogger(__name__)


class eovpn(Base):
    """
    Main application wrapper controlling initialization and UI display.
    کلاس مدیریت اصلی جهت بارگذاری رابط کاربری و تنظیمات زبان.
    """

    def __init__(self, app: Gtk.Application):
        super(eovpn, self).__init__()
        self.app = app

    def start(self):
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


def on_activate(app: Gtk.Application):
    main = eovpn(app)
    main.start()


def launch_eovpn() -> int:
    """
    Primary entry point invoked by the executable binary.
    نقطه ورود اصلی فراخوانی‌شده توسط فایل اجرایی برنامه.
    """
    app = Gtk.Application(
        application_id='com.github.mahdi-arts.eovpn-pro',
        flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
    )

    app.add_main_option(
        "debug", ord("d"), GLib.OptionFlags.NONE,
        GLib.OptionArg.STRING, "Show Debug Messages.", "[CRITICAL|ERROR|WARNING|INFO|DEBUG]"
    )

    app.connect('activate', on_activate)
    app.connect('command-line', do_command_line)

    # Strip legacy command-line flags that GLib option parsing does not
    # understand, so they cannot cause a startup failure.
    # حذف آرگومان‌های قدیمی که پارسر GLib آن‌ها را نمی‌شناسد تا باعث خطای راه‌اندازی نشوند
    for legacy_flag in ("-c", "--config"):
        if legacy_flag in sys.argv:
            sys.argv.remove(legacy_flag)

    return app.run(sys.argv)


def do_command_line(app: Gtk.Application, args: Gio.ApplicationCommandLine) -> bool:
    options_dict = args.get_options_dict()

    if options_dict.contains("debug"):
        debug_val = options_dict.lookup_value("debug", None)
        if debug_val:
            debug_lvl = debug_val.get_string()
            if debug_lvl.isnumeric():
                lvl_int = int(debug_lvl)
                if lvl_int <= 50:
                    logging.basicConfig(
                        level=lvl_int, format='%(levelname)s:%(name)s.py:%(funcName)s:%(message)s'
                    )
            elif debug_lvl in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]:
                logging.basicConfig(
                    level=debug_lvl, format='%(levelname)s:%(name)s.py:%(funcName)s:%(message)s'
                )

    app.activate()
    return True
