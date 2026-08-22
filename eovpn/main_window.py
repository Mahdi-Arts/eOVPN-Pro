"""
eOVPN-Pro Primary Main Window Controller
کنترلر اصلی پنجره رابط کاربری در eOVPN-Pro

Manages VPN configuration list presentation, live bandwidth monitoring,
concurrent speed tests, latency-based sorting, and connection orchestration.
مدیریت لیست کانفیگ‌ها، مانیتورینگ زنده ترافیک کارت شبکه، تست پینگ همزمان و اتصال به VPN.
"""

import os
import logging
import gettext
import webbrowser
import threading
from time import sleep

from gi.repository import Gtk, Gio, GLib, Gdk, Adw

from .settings_window import SettingsWindow
from .connection_manager import NetworkManager, OpenVPN3
from .ip_lookup.lookup import Lookup
from .utils import ovpn_is_auth_required
from .eovpn_base import Base, StorageItem, ConfigRow

logger = logging.getLogger(__name__)


class MainWindow(Base, Gtk.Builder):
    """
    Main application window combining configuration selector and traffic monitor.
    پنجره اصلی برنامه شامل لیست کانفیگ‌ها، کارت آمار مصرف ترافیک و گزینه‌های اتصال.
    """
    def __init__(self, app: Gtk.Application):
        super().__init__()
        Gtk.Builder.__init__(self)
        self.app = app
        
        if self.get_setting(self.SETTING.DARK_THEME) is True:
            gtk_settings = Gtk.Settings().get_default()
            if gtk_settings:
                gtk_settings.set_property("gtk-application-prefer-dark-theme", True)

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/main.ui")
        self.window = self.get_object("main_window")
        self.window.set_title(self.APP_NAME)
        self.window.set_icon_name(self.APP_ID)

        self.toast_overlay = Adw.ToastOverlay()

        self.app.add_window(self.window)
        self.store(StorageItem.MAIN_WINDOW, self.window)
        self.store("main_window_instance", self)

        self.selected_row: ConfigRow | None = None
        self.manual_disconnect = False
        self.selected_config = None
        self.connected_cursor = None
        self.signals = Signals()
        self.latencies: dict[str, float | None] = {}
        self.sort_by_speed_active = False

        ###########################################################
        # Initialize and setup Connection Manager (CM)
        # مقداردهی اولیه مدیریت‌کننده اتصالات
        ###########################################################
        preferred = self.get_setting(self.SETTING.MANAGER)
        self.store("CM", {
            "name": preferred,
            "instance": NetworkManager(self.on_connection_event)
            if preferred == "networkmanager"
            else OpenVPN3(self.on_connection_event)
        })
        self.store("on_connection_event", self.on_connection_event)
        self.CM = lambda: self.retrieve("CM")["instance"]

        self.lookup = Lookup()

    def get_selected_config(self) -> str | None:
        """
        Retrieves the filename of the currently selected configuration.
        دریافت نام فایل کانکشن انتخاب‌شده در لیست.
        """
        selected_row = self.list_box.get_selected_row()
        if not selected_row:
            return None
        if hasattr(selected_row, "filename"):
            self.selected_row = selected_row
            selected_row.set_edit_visible(True)
            return selected_row.filename
        return None

    def row_changed(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None):
        """
        Handles list row selection changes and validates authentication requirements.
        مدیریت تغییر ردیف انتخابی و بررسی نیازمندی‌های نام کاربری و کلمه عبور.
        """
        if self.selected_row and hasattr(self.selected_row, "set_edit_visible"):
            try:
                self.selected_row.set_edit_visible(False)
            except Exception:
                pass

        self.selected_row = row
        if row and hasattr(row, "set_edit_visible"):
            row.set_edit_visible(True)

        if (selected := self.get_selected_config()) is not None:
            if self.get_setting(self.SETTING.REQ_AUTH) is True:
                config_path = os.path.join(self.EOVPN_OVPN_CONFIG_DIR, selected)
                if ovpn_is_auth_required(config_path) and self.get_setting(self.SETTING.AUTH_USER) is None:
                    self.connect_btn.set_sensitive(False)
                    self.connect_btn.set_tooltip_text(gettext.gettext("Authentication Required!"))
                    return

        self.connect_btn.set_sensitive(True)
        self.connect_btn.set_tooltip_text("")

    def generic_critical_error_dialog(self, error_message: list[str]):
        """
        Displays a critical modal error dialog.
        نمایش دیالوگ خطای بحرانی.
        """
        def cb(dialog, res):
            Gio.Application.quit(self.app)

        dlg = Gtk.MessageDialog()
        dlg.set_transient_for(self.window)
        dlg.set_modal(True)

        dlg.set_property("message-type", Gtk.MessageType.ERROR)
        dlg.set_property("use-markup", True)
        dlg.set_property("text", "<span weight='bold'>Error</span>")
        dlg.connect("response", cb)

        btn = dlg.add_button(gettext.gettext("Exit"), 1)
        btn.add_css_class("destructive-action")

        box = dlg.get_message_area()
        for msg in error_message:
            box.append(Gtk.Label.new(msg))
        dlg.show()

    def setup(self):
        """
        Constructs and wires the full user interface.
        ساخت و اتصال اجزای رابط کاربری.
        """
        self.box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.inner_left = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.inner_right = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)

        def update_layout():
            if self.get_setting(self.SETTING.LAYOUT) == "card-h":
                self.paned.set_orientation(Gtk.Orientation.HORIZONTAL)
                self.inner_left.set_size_request(220, -1)
                self.window.set_default_size(800, 400)
            else:
                self.paned.set_orientation(Gtk.Orientation.VERTICAL)
                self.inner_left.set_size_request(-1, 120)
                self.window.set_default_size(400, 800)
        
        update_layout()
        self.paned.set_start_child(self.inner_left)
        self.paned.set_end_child(self.inner_right)

        # ---------------------------------------------------------
        # Left Panel (Configurations & Speed Test Toolbar)
        # پنل سمت چپ (لیست کانفیگ‌ها و نوار ابزار تست سرعت)
        # ---------------------------------------------------------
        viewport = Gtk.Viewport.new()
        viewport.set_vexpand(True)
        viewport.set_hexpand(True)

        self.scrolled_window = Gtk.ScrolledWindow.new()

        self.list_box = Gtk.ListBox.new()
        self.list_box.connect("row-selected", self.row_changed)
        self.store(StorageItem.LISTBOX, self.list_box)

        # Placeholder when list is empty / ویجت جایگزین در زمان خالی بودن لیست
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        v_box.set_valign(Gtk.Align.CENTER)
        lbl = Gtk.Label.new(gettext.gettext("No Configs Added!"))
        lbl.add_css_class("bold")
        btn = Gtk.Button.new_with_label(gettext.gettext("Open Settings"))
        btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.START)
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda x: SettingsWindow().show())
        v_box.append(lbl)
        v_box.append(btn)
        self.list_box.set_placeholder(v_box)

        self.scrolled_window.set_child(viewport)
        viewport.set_child(self.list_box)
        self.load_only()

        # Set up sorting function / مرتب‌سازی هوشمند
        self.list_box.set_sort_func(self.list_box_sort_func)

        # Pro Features Toolbar / نوار ابزار قابلیت‌های حرفه‌ای
        self.pro_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        self.pro_box.set_margin_start(10)
        self.pro_box.set_margin_end(10)
        self.pro_box.set_margin_top(6)
        self.pro_box.set_margin_bottom(6)
        self.pro_box.add_css_class("linked")

        self.speed_test_btn = Gtk.Button.new_with_label(gettext.gettext("Speed Test"))
        self.speed_test_btn.set_tooltip_text(gettext.gettext("Test latency of all VPN servers"))
        self.speed_test_btn.connect("clicked", lambda b: self.trigger_speed_test())

        self.sort_btn = Gtk.ToggleButton.new_with_label(gettext.gettext("Sort"))
        self.sort_btn.set_tooltip_text(gettext.gettext("Sort servers by lowest latency"))
        self.sort_btn.connect("toggled", self.on_sort_toggled)

        self.fastest_btn = Gtk.Button.new_with_label(gettext.gettext("Select Fastest"))
        self.fastest_btn.set_tooltip_text(gettext.gettext("Auto-select server with the lowest latency"))
        self.fastest_btn.connect("clicked", self.select_fastest)

        self.pro_box.append(self.speed_test_btn)
        self.pro_box.append(self.sort_btn)
        self.pro_box.append(self.fastest_btn)

        self.inner_left.append(self.pro_box)
        self.inner_left.append(self.scrolled_window)

        # ---------------------------------------------------------
        # Right Panel (Status, IP, Traffic Card, and Connect Button)
        # پنل سمت راست (وضعیت، آدرس آی‌پی، کارت مانیتورینگ و دکمه اتصال)
        # ---------------------------------------------------------
        img = Gtk.Picture.new()
        img.set_halign(Gtk.Align.CENTER)
        img.set_valign(Gtk.Align.CENTER)
        img.add_css_class("rounded")
        self.store(StorageItem.FLAG, img)
        if self.get_setting(self.SETTING.SHOW_FLAG) is False:
            img.hide()
        self.inner_right.append(img)

        # IP Address & Geolocation info / اطلاعات آی‌پی
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        h_box.set_halign(Gtk.Align.CENTER)
        self.ip_text = Gtk.Label.new(gettext.gettext("IP: "))
        self.ip_addr = Gtk.Label.new("0.0.0.0")
        self.ip_addr.set_valign(Gtk.Align.CENTER)
        self.ip_addr.add_css_class("ip_text")
        self.ip_addr.set_vexpand(True)
        cpy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        cpy_btn.set_valign(Gtk.Align.CENTER)
        cpy_btn.set_halign(Gtk.Align.CENTER)
        cpy_btn.set_tooltip_text(gettext.gettext("Copy IP Address"))
        cpy_btn.add_css_class("flat")

        h_box.append(self.ip_text)
        h_box.append(self.ip_addr)
        h_box.append(cpy_btn)
        self.inner_right.append(h_box)

        # Traffic & Speed Card Panel / کادر مدرن مانیتورینگ ترافیک زنده
        self.traffic_card = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        self.traffic_card.add_css_class("card")
        self.traffic_card.add_css_class("traffic-card")
        self.traffic_card.set_halign(Gtk.Align.CENTER)
        self.traffic_card.set_size_request(300, 72)
        self.traffic_card.set_margin_top(12)
        self.traffic_card.set_margin_bottom(12)
        self.traffic_card.set_tooltip_text(gettext.gettext("Live traffic statistics for the active VPN tunnel"))

        def build_stat_cell(icon_name: str, css_variant: str, caption_text: str):
            cell = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 8)
            cell.set_hexpand(True)
            cell.set_halign(Gtk.Align.CENTER)
            cell.set_valign(Gtk.Align.CENTER)

            badge = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
            badge.add_css_class("traffic-icon-badge")
            badge.add_css_class(css_variant)
            badge.set_halign(Gtk.Align.CENTER)
            badge.set_valign(Gtk.Align.CENTER)
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(15)
            badge.append(icon)

            text_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
            text_box.set_valign(Gtk.Align.CENTER)
            value_label = Gtk.Label.new("0.0 B/s")
            value_label.add_css_class("traffic-value")
            value_label.set_halign(Gtk.Align.START)
            value_label.set_xalign(0.0)
            caption_label = Gtk.Label.new(caption_text)
            caption_label.add_css_class("traffic-caption")
            caption_label.add_css_class("dim-label")
            caption_label.set_halign(Gtk.Align.START)
            caption_label.set_xalign(0.0)
            text_box.append(value_label)
            text_box.append(caption_label)

            cell.append(badge)
            cell.append(text_box)
            return cell, value_label

        dl_cell, self.dl_speed_label = build_stat_cell(
            "network-receive-symbolic", "traffic-icon-download", gettext.gettext("Download"))
        ul_cell, self.ul_speed_label = build_stat_cell(
            "network-transmit-symbolic", "traffic-icon-upload", gettext.gettext("Upload"))
        total_cell, self.total_traffic_label = build_stat_cell(
            "utilities-system-monitor-symbolic", "traffic-icon-total", gettext.gettext("Total"))
        self.total_traffic_label.set_text("0 B")

        self.traffic_card.append(dl_cell)
        self.traffic_card.append(Gtk.Separator.new(Gtk.Orientation.VERTICAL))
        self.traffic_card.append(ul_cell)
        self.traffic_card.append(Gtk.Separator.new(Gtk.Orientation.VERTICAL))
        self.traffic_card.append(total_cell)

        self.inner_right.append(self.traffic_card)

        self.psh = None

        self.connect_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        self.connect_box.set_valign(Gtk.Align.END)
        self.connect_box.add_css_class("m-10")
        self.connect_btn = Gtk.Button.new_with_label(gettext.gettext("Connect"))
        self.connect_btn.set_valign(Gtk.Align.FILL)
        self.connect_btn.set_hexpand(True)
        self.connect_btn.set_vexpand(True)
        
        self.connect_box.append(self.connect_btn)

        self.pause_resume_btn = Gtk.Button.new_from_icon_name("media-playback-pause-symbolic")
        self.pause_resume_btn.set_valign(Gtk.Align.END)
        self.pause_resume_btn.set_vexpand(True)
        self.pause_resume_btn.set_visible(False)

        self.connect_btn.connect("clicked", self.signals.connect, self.get_selected_config)
        self.swap_pause_btn_signal_resume_to_pause()

        self.connect_box.append(self.pause_resume_btn)
        self.inner_right.append(self.connect_box)

        # ---------------------------------------------------------
        # Bottom Progress Bar / نوار پیشرفت پایین
        # ---------------------------------------------------------
        self.progress_bar = Gtk.ProgressBar.new()
        
        if self.CM().status():
            self.connect_btn.set_label(gettext.gettext("Disconnect"))
            self.connect_btn.add_css_class("destructive-action")
            self.progress_bar.add_css_class("progress-full-green")
            self.progress_bar.set_fraction(1.0)
        else:
            self.progress_bar.add_css_class("progress-yellow")

        def open_about_dialog(widget, data):
            about = Gtk.AboutDialog.new()
            about.set_logo_icon_name(self.APP_ID)
            about.set_program_name(self.APP_NAME)
            about.set_authors([self.AUTHOR])
            about.set_artists([self.AUTHOR])
            about.set_copyright(self.AUTHOR)
            about.set_license_type(Gtk.License.LGPL_3_0)
            about.set_version(self.APP_VERSION)
            website = self.AUTHOR_WEBSITE
            if not website.startswith("http"):
                website = "https://" + website
            about.set_website(website)
            about.set_system_information("Flatpak: \t {}\nCommit: \t {}".format(
                "true" if os.getenv("FLATPAK_ID") is not None else "false", self.APP_COMMIT))
            about.set_transient_for(self.window)
            about.set_modal(True)
            about.show()

        def open_ks(widget, data):
            builder = Gtk.Builder()
            builder.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/keyboard_shortcuts.ui")
            window = builder.get_object("shortcuts_window")
            window.set_transient_for(self.window)
            window.set_modal(True)
            window.show()

        def on_layout_update(action, value):
            logger.info("Layout updated to: %s", value)
            action.set_state(value)
            self.set_setting(self.SETTING.LAYOUT, str(value).replace("'", ""))
            update_layout()

        action = Gio.SimpleAction.new_stateful(
            "radiogroup",
            GLib.VariantType.new("s"),
            GLib.Variant("s", self.get_setting(self.SETTING.LAYOUT))
        )
        action.connect("activate", on_layout_update)
        self.app.add_action(action)

        def on_language_update(action, value):
            new_lang = str(value).replace("'", "")
            logger.info("Changing language to: %s", new_lang)
            action.set_state(value)
            self.set_setting(self.SETTING.LANGUAGE, new_lang)
            import sys
            os.execv(sys.executable, [sys.executable] + sys.argv)

        action_lang = Gio.SimpleAction.new_stateful(
            "language",
            GLib.VariantType.new("s"),
            GLib.Variant("s", self.get_setting(self.SETTING.LANGUAGE) or "en")
        )
        action_lang.connect("activate", on_language_update)
        self.app.add_action(action_lang)

        action = Gio.SimpleAction.new("update", None)
        action.connect("activate", lambda x, d: self.validate_and_load(self.spinner))
        self.app.add_action(action)

        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", open_about_dialog)
        self.app.add_action(action)

        action = Gio.SimpleAction.new("donate", None)
        action.connect("activate", lambda x, d: webbrowser.open(self.AUTHOR_DONATE))
        self.app.add_action(action)

        action = Gio.SimpleAction.new("keyboard_shortcuts", None)
        action.connect("activate", open_ks)
        self.app.add_action(action)

        action = Gio.SimpleAction.new("settings", None)
        action.connect("activate", lambda x, d: SettingsWindow().show())
        self.app.add_action(action)

        # Shortcuts / کلیدهای میانبر
        self.app.set_accels_for_action("app.keyboard_shortcuts", ["<Primary>question"])
        self.app.set_accels_for_action("app.settings", ["<Primary>S"])
        self.app.set_accels_for_action("app.update", ["<Primary>U"])
        self.app.set_accels_for_action("app.about", ["<Primary>A"])
        
        action = Gio.SimpleAction.new("connect", None)
        action.connect('activate', self.signals.connect_via_ks, self.get_selected_config)
        self.app.add_action(action)
        self.app.set_accels_for_action("app.connect", ["<Primary>C", "<Primary>D"])

        menu = Gio.Menu()
        layout_menu = Gio.Menu()
        item = Gio.MenuItem.new(gettext.gettext("Vertical"), "card-v")
        item.set_action_and_target_value("app.radiogroup", GLib.Variant.new_string("card-v"))
        layout_menu.append_item(item)

        item = Gio.MenuItem.new(gettext.gettext("Horizontal"), "card-h")
        item.set_action_and_target_value("app.radiogroup", GLib.Variant.new_string("card-h"))
        layout_menu.append_item(item)
        
        lang_menu = Gio.Menu()
        item = Gio.MenuItem.new("English", "en")
        item.set_action_and_target_value("app.language", GLib.Variant.new_string("en"))
        lang_menu.append_item(item)

        item = Gio.MenuItem.new("فارسی (Persian)", "fa")
        item.set_action_and_target_value("app.language", GLib.Variant.new_string("fa"))
        lang_menu.append_item(item)

        menu.append(gettext.gettext("Update"), "app.update")
        menu.append(gettext.gettext("Settings"), "app.settings")
        menu.append(gettext.gettext("Keyboard Shortcuts"), "app.keyboard_shortcuts")
        menu.append_submenu(gettext.gettext("Layout"), layout_menu)
        menu.append_submenu(gettext.gettext("Language"), lang_menu)
        menu.append(gettext.gettext("Donate"), "app.donate")
        menu.append(gettext.gettext("About"), "app.about")
        popover = Gtk.PopoverMenu.new_from_model(menu)

        header_bar = self.get_object("header_bar")

        menu_button = Gtk.MenuButton.new()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_popover(popover)
        header_bar.pack_end(menu_button)

        # Dedicated Sponsor/Donate Button (❤️)
        self.donate_btn_header = Gtk.Button.new_from_icon_name("emblem-favorite-symbolic")
        self.donate_btn_header.set_tooltip_text(gettext.gettext("Sponsor & Donate (حمایت مالی)"))
        self.donate_btn_header.add_css_class("flat")
        self.donate_btn_header.connect("clicked", lambda b: webbrowser.open(self.AUTHOR_DONATE))
        header_bar.pack_end(self.donate_btn_header)

        self.spinner = Gtk.Spinner()
        header_bar.pack_end(self.spinner)

        if (cur := self.get_setting(self.SETTING.LAST_CONNECTED_CURSOR)) != -1:
            try:
                rows = self.retrieve(StorageItem.LISTBOX_ROWS)
                if rows and cur < len(rows):
                    self.list_box.select_row(rows[cur])
                adj = self.scrolled_window.get_vadjustment()
                v = self.get_setting(self.SETTING.LISTBOX_V_ADJUST)
                if v is not None:
                    adj.set_value(v)
            except Exception as e:
                logger.error("Error restoring cursor: %s", e)

        self.box.append(self.paned)
        self.box.append(self.progress_bar)
        self.toast_overlay.set_child(self.box)
        self.window.set_child(self.toast_overlay)

        def copy_ip(btn: Gtk.Button):
            toast = Adw.Toast.new(gettext.gettext("IP Address copied to Clipboard!"))
            toast.set_timeout(1)
            clipboard = Gdk.Display.get_default().get_clipboard()
            if clipboard:
                clipboard.set(self.ip_addr.get_label())
            self.toast_overlay.add_toast(toast)

        cpy_btn.connect("clicked", copy_ip)

    def list_box_sort_func(self, row1: Gtk.ListBoxRow, row2: Gtk.ListBoxRow, *args) -> int:
        """
        Sorts the configuration list alphabetically or by measured latency.
        مرتب‌سازی هوشمند لیست کانفیگ‌ها بر اساس حروف الفبا یا کمترین پینگ.
        """
        file1 = getattr(row1, "filename", "")
        file2 = getattr(row2, "filename", "")
        if not file1 or not file2:
            return 0

        if not getattr(self, "sort_by_speed_active", False):
            return 1 if file1 > file2 else -1

        rtt1 = self.latencies.get(file1, None)
        rtt2 = self.latencies.get(file2, None)

        if rtt1 is None and rtt2 is None:
            return 1 if file1 > file2 else -1
        if rtt1 is None:
            return 1
        if rtt2 is None:
            return -1

        if rtt1 < rtt2:
            return -1
        elif rtt1 > rtt2:
            return 1
        else:
            return 1 if file1 > file2 else -1

    def trigger_speed_test(self):
        """
        Initiates concurrent latency test for all available .ovpn endpoints.
        آغاز تست پینگ موازی برای کلیه سرورهای موجود در کانفیگ‌ها.
        """
        if not getattr(self, "speed_test_btn", None) or not self.speed_test_btn.get_sensitive():
            return
        self.speed_test_btn.set_sensitive(False)
        self.speed_test_btn.set_label(gettext.gettext("Testing..."))
        self.spinner.start()

        def worker():
            from .speed_test import test_all_configs
            configs_list = self.retrieve(StorageItem.CONFIGS_LIST)
            latencies = test_all_configs(self.EOVPN_OVPN_CONFIG_DIR, configs_list)
            GLib.idle_add(self.on_speed_test_complete, latencies)

        th = threading.Thread(target=worker)
        th.daemon = True
        th.start()

    def on_speed_test_complete(self, latencies: dict[str, float | None]):
        """
        Updates latency labels in UI and applies sorting once speed test finishes.
        به‌روزرسانی برچسب‌های پینگ در رابط کاربری و اعمال مرتب‌سازی خودکار پس از اتمام تست.
        """
        self.latencies = latencies
        latency_labels = self.retrieve("latency_labels")

        for file, rtt in latencies.items():
            if file in latency_labels:
                label_widget = latency_labels[file]
                if rtt is not None:
                    if rtt < 100:
                        label_widget.set_markup(f"<span foreground='#2ec27e' weight='bold'>{rtt} ms</span>")
                    elif rtt < 250:
                        label_widget.set_markup(f"<span foreground='#e5a50a' weight='bold'>{rtt} ms</span>")
                    else:
                        label_widget.set_markup(f"<span foreground='#e01b24' weight='bold'>{rtt} ms</span>")
                else:
                    label_widget.set_markup("<span foreground='#e01b24' alpha='60%'>Error</span>")

        if self.sort_by_speed_active:
            self.list_box.invalidate_sort()

        self.speed_test_btn.set_sensitive(True)
        self.speed_test_btn.set_label(gettext.gettext("Speed Test"))
        self.spinner.stop()

        if getattr(self, "auto_select_after_test", False):
            self.auto_select_after_test = False
            self.select_fastest(None)

    def on_sort_toggled(self, button: Gtk.ToggleButton):
        """
        Toggles dynamic speed sorting on/off.
        فعال یا غیرفعال کردن مرتب‌سازی پویا بر اساس پینگ سرور.
        """
        self.sort_by_speed_active = button.get_active()
        if self.sort_by_speed_active:
            button.add_css_class("suggested-action")
            if not self.latencies:
                self.trigger_speed_test()
        else:
            button.remove_css_class("suggested-action")
        self.list_box.invalidate_sort()

    def select_fastest(self, button: Gtk.Button | None):
        """
        Finds and auto-selects the server configuration with the lowest latency.
        شناسایی و انتخاب خودکار سریع‌ترین سرور در لیست کانفیگ‌ها.
        """
        if not self.latencies:
            self.auto_select_after_test = True
            self.trigger_speed_test()
            return

        valid_latencies = {k: v for k, v in self.latencies.items() if v is not None}
        if not valid_latencies:
            toast = Adw.Toast.new(gettext.gettext("No reachable servers found! Please run speed test."))
            self.toast_overlay.add_toast(toast)
            return

        fastest_file = min(valid_latencies, key=valid_latencies.get)

        configs_list = self.retrieve(StorageItem.CONFIGS_LIST)
        try:
            idx = configs_list.index(fastest_file)
            rows = self.retrieve(StorageItem.LISTBOX_ROWS)
            if idx < len(rows):
                row_to_select = rows[idx]
                self.list_box.select_row(row_to_select)

            toast = Adw.Toast.new(
                gettext.gettext("Selected fastest server: {} ({} ms)").format(
                    fastest_file, valid_latencies[fastest_file]
                )
            )
            self.toast_overlay.add_toast(toast)
        except Exception as e:
            logger.error("Error selecting fastest server: %s", e)

    def start_network_monitor(self):
        """Starts real-time bandwidth monitoring."""
        self.stop_network_monitor()
        self.last_rx = 0
        self.last_tx = 0
        import time as pytime
        self.last_time = pytime.time()
        self.network_monitor_id = GLib.timeout_add_seconds(1, self.update_network_speed)

    def stop_network_monitor(self):
        """Stops real-time bandwidth monitoring."""
        if hasattr(self, "network_monitor_id") and self.network_monitor_id:
            GLib.source_remove(self.network_monitor_id)
            self.network_monitor_id = None

    def update_network_speed(self) -> bool:
        """
        Reads kernel network statistics from /proc/net/dev and calculates live throughput.
        محاسبه نرخ لحظه‌ای دانلود و آپلود از شمارنده‌های هسته لینوکس.
        """
        try:
            rx, tx = 0, 0
            if os.path.exists("/proc/net/dev"):
                with open("/proc/net/dev", "r") as f:
                    for line in f:
                        if ":" in line:
                            parts = line.split(":")
                            if len(parts) == 2:
                                if any(x in parts[0] for x in ["tun", "tap", "ovpn", "ppp", "wg"]):
                                    stats = parts[1].split()
                                    rx += int(stats[0])
                                    tx += int(stats[8])

            if rx == 0 and tx == 0:
                if os.path.exists("/proc/net/dev"):
                    with open("/proc/net/dev", "r") as f:
                        for line in f:
                            if ":" in line:
                                parts = line.split(":")
                                if len(parts) == 2:
                                    if "lo" not in parts[0]:
                                        stats = parts[1].split()
                                        rx += int(stats[0])
                                        tx += int(stats[8])

            import time as pytime
            now = pytime.time()
            dt = now - getattr(self, "last_time", now - 1.0)
            if dt <= 0:
                dt = 1.0

            last_rx = getattr(self, "last_rx", 0)
            last_tx = getattr(self, "last_tx", 0)

            if last_rx > 0 and last_tx > 0:
                dl_speed = (rx - last_rx) / dt
                ul_speed = (tx - last_tx) / dt

                def format_speed(bytes_per_sec: float) -> str:
                    if bytes_per_sec < 1024:
                        return f"{bytes_per_sec:.1f} B/s"
                    elif bytes_per_sec < 1024 * 1024:
                        return f"{bytes_per_sec / 1024:.1f} KB/s"
                    else:
                        return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"

                def format_size(bytes_total: float) -> str:
                    if bytes_total < 1024:
                        return f"{bytes_total} B"
                    elif bytes_total < 1024 * 1024:
                        return f"{bytes_total / 1024:.1f} KB"
                    elif bytes_total < 1024 * 1024 * 1024:
                        return f"{bytes_total / (1024 * 1024):.1f} MB"
                    else:
                        return f"{bytes_total / (1024 * 1024 * 1024):.1f} GB"

                self.dl_speed_label.set_text(format_speed(dl_speed))
                self.ul_speed_label.set_text(format_speed(ul_speed))
                self.total_traffic_label.set_text(format_size(rx + tx))

            self.last_rx = rx
            self.last_tx = tx
            self.last_time = now
        except Exception as e:
            logger.error("Error in network monitor: %s", e)

        return True

    def trigger_reconnect(self) -> bool:
        """Schedules automated reconnection."""
        selected = self.get_selected_config()
        if selected:
            logger.info("Auto-reconnecting to %s", selected)
            self.signals.connect(None, self.get_selected_config)
        return False

    def update_set_ip_flag(self):
        """Updates public IP and country flag asynchronously."""
        self.spinner.start()
        if os.environ.get("FLATPAK_ID") is not None:
            sleep(1.25)
        self.lookup.update()
        self.retrieve(StorageItem.FLAG).set_pixbuf(self.get_country_pixbuf(self.lookup.country_code))
        self.ip_addr.set_label(self.lookup.ip or "0.0.0.0")
        self.spinner.stop()

    def swap_pause_btn_signal_pause_to_resume(self):
        self.pause_resume_btn.set_property("icon-name", "media-playback-start-symbolic")
        if self.psh is not None:
            self.pause_resume_btn.disconnect(self.psh)
        self.psh = self.pause_resume_btn.connect("clicked", self.signals.resume, self.CM())
        self.update_ip_flag_async()
        
    def swap_pause_btn_signal_resume_to_pause(self):
        self.pause_resume_btn.set_property("icon-name", "media-playback-pause-symbolic")
        if self.psh is not None:
            self.pause_resume_btn.disconnect(self.psh)
        self.psh = self.pause_resume_btn.connect("clicked", self.signals.pause, self.CM())

    def on_connection_event(self, result, error=None):
        """
        Handles connection status transitions and D-Bus signals.
        مدیریت تغییرات وضعیت تونل VPN و پردازش رویدادهای D-Bus.
        """
        if error is not None:
            logger.error("Connection error: %s", error)
            self.send_error_notification(error)
            self.progress_bar.set_fraction(0)
            return

        if type(result) is list:
            if len(result) == 1:
                status = result[-1]

                if status == "pause":
                    self.progress_bar.remove_css_class("progress-full-green")
                    self.progress_bar.add_css_class("progress-orange")
                    self.swap_pause_btn_signal_pause_to_resume()
                    return

                elif status == "resume":
                    self.progress_bar.remove_css_class("progress-orange")
                    self.progress_bar.add_css_class("progress-full-green")
                    self.swap_pause_btn_signal_resume_to_pause()
                    return

            prev = self.progress_bar.get_fraction()
            if prev < 0.95:
                self.progress_bar.set_fraction(prev + 0.35)
            return

        if result:
            self.start_network_monitor()
            self.was_connected = True
            self.update_ip_flag_async()
            self.connect_btn.set_label(gettext.gettext("Disconnect"))
            self.connect_btn.add_css_class("destructive-action")

            self.progress_bar.remove_css_class("progress-yellow")
            self.progress_bar.remove_css_class("progress-orange")
            self.progress_bar.add_css_class("progress-full-green")

            self.progress_bar.set_fraction(1.0)
            self.set_setting(self.SETTING.LAST_CONNECTED, self.get_selected_config())
            self.send_connected_notification()
            
            # Save last cursor & vertical adjustment / ذخیره آخرین موقعیت نشانگر
            adj = self.scrolled_window.get_vadjustment()
            if adj:
                self.set_setting(self.SETTING.LISTBOX_V_ADJUST, float(adj.get_value()))
            
            configs = self.retrieve(StorageItem.CONFIGS_LIST)
            selected_cfg = self.get_selected_config()
            if configs and selected_cfg in configs:
                self.set_setting(self.SETTING.LAST_CONNECTED_CURSOR, configs.index(selected_cfg) - 1)
            
            self.swap_pause_btn_signal_resume_to_pause()

            if self.CM().get_name().lower() == "openvpn3":
                if self.CM().config_path is not None:
                    self.pause_resume_btn.set_visible(True)

        else:
            self.stop_network_monitor()
            self.dl_speed_label.set_text("0.0 B/s")
            self.ul_speed_label.set_text("0.0 B/s")
            self.total_traffic_label.set_text("0 B")

            should_reconnect = getattr(self, "was_connected", False) and self.get_setting(
                self.SETTING.AUTO_RECONNECT) and not getattr(self, "manual_disconnect", False)
            self.was_connected = False
            self.manual_disconnect = False

            self.update_ip_flag_async()
            self.connect_btn.set_label(gettext.gettext("Connect"))
            self.connect_btn.remove_css_class("destructive-action")
            self.progress_bar.remove_css_class("progress-full-green")
            self.progress_bar.add_css_class("progress-yellow")
            self.progress_bar.set_fraction(0)
            self.send_disconnected_notification()
            
            self.swap_pause_btn_signal_pause_to_resume()
            self.pause_resume_btn.set_visible(False)

            if should_reconnect:
                logger.info("Connection lost. Auto-reconnecting in 3 seconds...")
                toast = Adw.Toast.new(gettext.gettext("Connection lost. Reconnecting in 3 seconds..."))
                self.toast_overlay.add_toast(toast)
                GLib.timeout_add_seconds(3, self.trigger_reconnect)

    def show(self):
        """Displays main application window."""
        self.setup()
        self.update_ip_flag_async()
        if logger.getEffectiveLevel() == 10:
            self.window.add_css_class("devel")
        self.window.show()

    def update_ip_flag_async(self):
        """Runs IP and geolocation lookup asynchronously."""
        th = threading.Thread(target=self.update_set_ip_flag)
        th.daemon = True
        th.start()


class Signals(Base):
    """
    Action dispatchers for MainWindow buttons and accelerator shortcuts.
    سیستم مدیریت سیگنال‌ها و اکشن‌های پنجره اصلی.
    """

    def __init__(self):
        super().__init__()

    def connect(self, button, config_callable):
        manager = self.retrieve("CM")["instance"]
        manager.start_watch()
        if manager.status():
            self.disconnect(None, manager)
            return
        try:
            mw = self.retrieve("main_window_instance")
            if mw:
                mw.manual_disconnect = False
        except Exception:
            pass
        config = config_callable() if callable(config_callable) else config_callable
        if config:
            manager.connect(os.path.join(self.EOVPN_CONFIG_DIR, "CONFIGS", config))

    def connect_via_ks(self, action, _args, config_callable):
        self.connect(None, config_callable)

    def disconnect(self, button, manager):
        try:
            mw = self.retrieve("main_window_instance")
            if mw:
                mw.manual_disconnect = True
        except Exception:
            pass
        manager.disconnect()

    def pause(self, button, manager):
        if hasattr(manager, "pause"):
            manager.pause()   

    def resume(self, button, manager):
        if hasattr(manager, "resume"):
            manager.resume()
