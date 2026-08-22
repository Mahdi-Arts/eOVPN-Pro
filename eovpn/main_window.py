"""
eOVPN-Pro Primary Main Window Controller
کنترلر اصلی پنجره رابط کاربری در eOVPN-Pro

Manages VPN configuration list presentation, live bandwidth monitoring,
concurrent speed tests, latency-based sorting, and connection orchestration.
مدیریت لیست کانفیگ‌ها، مانیتورینگ زنده ترافیک کارت شبکه، تست پینگ همزمان و اتصال به VPN.
"""

import os
import sys
import time
import logging
import gettext
import webbrowser
import threading

from gi.repository import Gtk, Gio, GLib, Gdk, Adw, Pango

from .settings_window import SettingsWindow
from .connection_manager import NetworkManager, OpenVPN3
from .ip_lookup.lookup import Lookup
from .utils import matches_server_filter, ovpn_is_auth_required
from .eovpn_base import Base, StorageItem, ConfigRow
from .auto_connect import (
    CascadePhase,
    DISCONNECT_SETTLE_SECONDS,
    MAX_CASCADE_CANDIDATES,
    PROGRESS_TICK_MS,
    PROTO_ALL,
    PROTO_TCP,
    PROTO_UDP,
    build_cascade_queue,
    collect_visible_filenames,
    compute_attempt_timeout,
    format_proto_badge,
    parse_ovpn_protocols,
)

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
        self.signals = MainWindowSignals()
        self.latencies: dict[str, float | None] = {}
        self.sort_by_speed_active = False

        # Search / Filter state / وضعیت جستجو و فیلتر لیست
        self.search_text: str = ""
        self.filter_mode: str = "all"
        self.proto_mode: str = PROTO_ALL

        # Cascading auto-connect state / وضعیت اتصال آبشاری به سریع‌ترین‌ها
        self._cascade_active = False
        self._cascade_gen = 0
        self._cascade_queue: list[str] = []
        self._cascade_index = 0
        self._cascade_phase = CascadePhase.IDLE
        self._cascade_deadline = 0.0
        self._cascade_timeout_id = None
        self._cascade_tick_id = None
        self._cascade_settle_id = None
        self._cascade_expect_disconnect = False
        self._cascade_current: str | None = None
        self._cascade_failures: list[tuple[str, str]] = []
        self.auto_cascade_after_test = False

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

        # Search & Filter infrastructure / زیرساخت جستجو و فیلتر هوشمند
        self.list_filter = Gtk.CustomFilter.new(self.list_filter_match, None, None)
        self.filter_model = Gtk.FilterListModel.new(None, self.list_filter)
        self.store("filter_model", self.filter_model)
        self.store("list_filter", self.list_filter)
        self.store("favorite_toggled_cb", self.on_favorite_toggled)
        self.store("on_list_changed", self.update_filter_count)

        # Placeholder when list is empty / ویجت جایگزین در زمان خالی بودن لیست
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        v_box.set_valign(Gtk.Align.CENTER)
        self.empty_label = Gtk.Label.new(gettext.gettext("No Configs Added!"))
        self.empty_label.add_css_class("bold")
        self.empty_btn = Gtk.Button.new_with_label(gettext.gettext("Open Settings"))
        self.empty_btn.add_css_class("suggested-action")
        self.empty_btn.set_valign(Gtk.Align.START)
        self.empty_btn.set_halign(Gtk.Align.CENTER)
        self.empty_btn.connect("clicked", lambda x: SettingsWindow().show())
        v_box.append(self.empty_label)
        v_box.append(self.empty_btn)
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

        self.fastest_btn = Gtk.Button.new_with_label(gettext.gettext("Connect Fastest"))
        self.fastest_btn.set_tooltip_text(gettext.gettext(
            "Connect to the first server in the current sorted and filtered list. "
            "If the handshake times out or fails, automatically try the next one."
        ))
        self.fastest_btn.add_css_class("suggested-action")
        self.fastest_btn.connect("clicked", self.on_fastest_clicked)

        self.pro_box.append(self.speed_test_btn)
        self.pro_box.append(self.sort_btn)
        self.pro_box.append(self.fastest_btn)

        # ---------------------------------------------------------
        # Search & Filter Toolbar / نوار ابزار جستجو و فیلتر سرورها
        # ---------------------------------------------------------
        self.filter_bar = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        self.filter_bar.set_margin_start(10)
        self.filter_bar.set_margin_end(10)
        self.filter_bar.set_margin_bottom(6)

        self.search_entry = Gtk.SearchEntry.new()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text(gettext.gettext("Search servers…"))
        self.search_entry.set_tooltip_text(gettext.gettext("Search configurations by name"))
        self.search_entry.connect("search-changed", self.on_search_changed)

        self.filter_dropdown = Gtk.DropDown.new(
            Gtk.StringList.new([
                gettext.gettext("All"),
                gettext.gettext("Favorites"),
                gettext.gettext("Online"),
                gettext.gettext("Offline"),
            ]),
            None,
        )
        self.filter_dropdown.set_selected(0)
        self.filter_dropdown.set_tooltip_text(gettext.gettext("Filter servers"))
        self.filter_dropdown.connect("notify::selected", self.on_filter_changed)

        self.proto_dropdown = Gtk.DropDown.new(
            Gtk.StringList.new([
                gettext.gettext("All Protocols"),
                "TCP",
                "UDP",
            ]),
            None,
        )
        self.proto_dropdown.set_selected(0)
        self.proto_dropdown.set_tooltip_text(
            gettext.gettext("Filter by OpenVPN protocol (TCP / UDP)")
        )
        self.proto_dropdown.connect("notify::selected", self.on_proto_filter_changed)

        self.filter_count = Gtk.Label.new("")
        self.filter_count.add_css_class("dim-label")
        self.filter_count.set_tooltip_text(
            gettext.gettext("Visible servers / Total servers")
        )

        self.filter_bar.append(self.search_entry)
        self.filter_bar.append(self.filter_dropdown)
        self.filter_bar.append(self.proto_dropdown)
        self.filter_bar.append(self.filter_count)

        # Cascade status banner / بنر وضعیت اتصال آبشاری
        self.cascade_revealer = Gtk.Revealer.new()
        self.cascade_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.cascade_revealer.set_transition_duration(220)
        self.cascade_revealer.set_reveal_child(False)

        self.cascade_banner = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        self.cascade_banner.add_css_class("cascade-banner")
        self.cascade_banner.set_margin_start(10)
        self.cascade_banner.set_margin_end(10)
        self.cascade_banner.set_margin_bottom(6)

        cascade_row = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 8)
        self.cascade_spinner = Gtk.Spinner.new()
        self.cascade_spinner.set_valign(Gtk.Align.CENTER)
        self.cascade_title = Gtk.Label.new("")
        self.cascade_title.set_hexpand(True)
        self.cascade_title.set_halign(Gtk.Align.START)
        self.cascade_title.set_xalign(0.0)
        self.cascade_title.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.cascade_title.add_css_class("cascade-title")
        self.cascade_meta = Gtk.Label.new("")
        self.cascade_meta.add_css_class("dim-label")
        self.cascade_meta.add_css_class("cascade-meta")
        self.cascade_cancel_btn = Gtk.Button.new_with_label(gettext.gettext("Cancel"))
        self.cascade_cancel_btn.add_css_class("destructive-action")
        self.cascade_cancel_btn.set_valign(Gtk.Align.CENTER)
        self.cascade_cancel_btn.connect("clicked", lambda *_: self.cancel_cascade(user=True))
        cascade_row.append(self.cascade_spinner)
        cascade_row.append(self.cascade_title)
        cascade_row.append(self.cascade_meta)
        cascade_row.append(self.cascade_cancel_btn)

        self.cascade_bar = Gtk.ProgressBar.new()
        self.cascade_bar.add_css_class("cascade-progress")
        self.cascade_bar.set_hexpand(True)

        self.cascade_banner.append(cascade_row)
        self.cascade_banner.append(self.cascade_bar)
        self.cascade_revealer.set_child(self.cascade_banner)

        self.inner_left.append(self.pro_box)
        self.inner_left.append(self.filter_bar)
        self.inner_left.append(self.cascade_revealer)
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
        self.traffic_card.set_tooltip_text(
            gettext.gettext("Live traffic statistics for the active VPN tunnel")
        )

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
            about.set_license_type(Gtk.License.GPL_3_0)
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
            # Restart the process so gettext picks up the new language
            # راه‌اندازی مجدد برنامه تا زبان جدید توسط gettext اعمال شود
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

        # Focus search box / تمرکز بر کادر جستجو
        action = Gio.SimpleAction.new("search", None)
        action.connect("activate", lambda *_: self.search_entry.grab_focus())
        self.app.add_action(action)
        self.app.set_accels_for_action("app.search", ["<Primary>F"])

        # Toggle favorites filter / تغییر وضعیت فیلتر موردعلاقه‌ها
        action = Gio.SimpleAction.new("toggle-favorites", None)
        action.connect("activate", lambda *_: self.toggle_favorites_filter())
        self.app.add_action(action)
        self.app.set_accels_for_action("app.toggle-favorites", ["<Primary><Shift>F"])

        # Cascading connect-to-fastest / اتصال آبشاری به سریع‌ترین سرور
        action = Gio.SimpleAction.new("connect-fastest", None)
        action.connect("activate", lambda *_: self.on_fastest_clicked(None))
        self.app.add_action(action)
        self.app.set_accels_for_action("app.connect-fastest", ["<Primary><Shift>C"])

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
                if rows and 0 <= cur < len(rows):
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

    # ------------------------------------------------------------------
    # Search, Filter & Favorites / جستجو، فیلتر و کانفیگ‌های مورد علاقه
    # ------------------------------------------------------------------

    def list_filter_match(self, item, *data) -> bool:
        """
        Filter callback used by Gtk.CustomFilter: combines the live search
        text, the selected filter mode and the favorites set.
        تابع فیلتر لیست که جستجوی زنده، حالت فیلتر و مجموعه موردعلاقه‌ها را ترکیب می‌کند.
        """
        filename = str(item)
        return matches_server_filter(
            filename,
            search=self.search_text,
            mode=self.filter_mode,
            favorites=self.get_favorites(),
            latencies=self.latencies,
            proto_mode=self.proto_mode,
            protocols=self._protocols_for(filename),
        )

    def on_search_changed(self, entry: Gtk.SearchEntry):
        """Re-applies the list filter on every keystroke."""
        self.search_text = entry.get_text().strip().lower()
        self._refresh_filter()

    def on_filter_changed(self, dropdown: Gtk.DropDown, *args):
        """Applies the selected filter mode (All / Favorites / Online / Offline)."""
        modes = ("all", "favorites", "online", "offline")
        idx = dropdown.get_selected()
        if idx < len(modes):
            self.filter_mode = modes[idx]
        self._refresh_filter()

    def on_proto_filter_changed(self, dropdown: Gtk.DropDown, *args):
        """Applies the TCP / UDP protocol filter / اعمال فیلتر پروتکل TCP یا UDP."""
        modes = (PROTO_ALL, PROTO_TCP, PROTO_UDP)
        idx = dropdown.get_selected()
        self.proto_mode = modes[idx] if 0 <= idx < len(modes) else PROTO_ALL
        self._refresh_filter()

    def _protocols_for(self, filename: str) -> frozenset[str]:
        """Cached proto set for a configuration / مجموعه پروتکل کش‌شده برای یک کانفیگ."""
        cache = self.retrieve("proto_cache")
        if not isinstance(cache, dict):
            cache = {}
            self.store("proto_cache", cache)
        if filename not in cache:
            cache[filename] = parse_ovpn_protocols(
                os.path.join(self.EOVPN_OVPN_CONFIG_DIR, filename)
            )
        return cache[filename]

    def toggle_favorites_filter(self):
        """Quickly toggles the favorites-only filter."""
        if self.filter_mode == "favorites":
            self.filter_mode = "all"
        else:
            self.filter_mode = "favorites"
        modes = ("all", "favorites", "online", "offline")
        self.filter_dropdown.set_selected(modes.index(self.filter_mode))
        self._refresh_filter()

    def _refresh_filter(self):
        """Notifies the filter model and updates the visible counter."""
        f = getattr(self, "list_filter", None)
        if f is not None:
            f.changed(Gtk.FilterChange.DIFFERENT)
        self.update_filter_count()

    def update_filter_count(self):
        """Shows 'visible / total' counters and adapts the empty-state message."""
        total = 0
        visible = 0
        try:
            total = len(self.retrieve(StorageItem.CONFIGS_LIST) or [])
            model = getattr(self, "filter_model", None)
            visible = model.get_n_items() if model is not None else total
        except Exception:
            pass
        if hasattr(self, "filter_count"):
            self.filter_count.set_text(f"{visible} / {total}")

        # Differentiate "no configs at all" from "nothing matches the filter"
        # تفکیک حالت «هیچ کانفیگی وجود ندارد» از «نتیجه‌ای با فیلتر پیدا نشد»
        if hasattr(self, "empty_label") and hasattr(self, "empty_btn"):
            if total == 0:
                self.empty_label.set_text(gettext.gettext("No Configs Added!"))
                self.empty_btn.set_visible(True)
            else:
                self.empty_label.set_text(gettext.gettext("No matching servers"))
                self.empty_btn.set_visible(False)

    def on_favorite_toggled(self, filename: str, active: bool):
        """Persists favorite state and live-updates the list filters."""
        self.toggle_favorite(filename, active)
        self._refresh_filter()

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

        # Re-evaluate Online/Offline filters with fresh latency data
        # بازارزیابی فیلترهای آنلاین/آفلاین با داده‌های تازه پینگ
        self._refresh_filter()

        self.speed_test_btn.set_sensitive(True)
        self.speed_test_btn.set_label(gettext.gettext("Speed Test"))
        self.spinner.stop()

        if getattr(self, "auto_cascade_after_test", False):
            self.auto_cascade_after_test = False
            if self._cascade_active and self._cascade_phase == CascadePhase.PREPARING:
                self._start_cascade_from_visible_list()
                return
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
        Selects (does not connect) the lowest-latency visible server.
        انتخاب (بدون اتصال) سرور با کمترین تأخیر در لیست نمایان.
        """
        valid_latencies = {k: v for k, v in self.latencies.items() if v is not None}
        if not valid_latencies:
            return None
        fastest_file = min(valid_latencies, key=valid_latencies.get)
        if self._select_server_by_name(fastest_file):
            return fastest_file
        return None

    # ------------------------------------------------------------------
    # Cascading connect-to-fastest / اتصال آبشاری به سریع‌ترین سرور
    # ------------------------------------------------------------------

    def on_fastest_clicked(self, button: Gtk.Button | None):
        """
        Starts or cancels the cascading auto-connect run.
        شروع یا لغو اتصال آبشاری به سرورهای لیست فعلی.
        """
        if self._cascade_active or getattr(self, "auto_cascade_after_test", False):
            self.cancel_cascade(user=True)
            return
        self.start_cascade()

    def start_cascade(self):
        """
        Connects from the first visible (sorted + filtered) server and walks
        down the list with a professional per-attempt handshake timeout.
        اتصال از اولین سرور نمایان و ادامه روی سرور بعدی در صورت شکست.
        """
        if self._cascade_active:
            return

        visible = collect_visible_filenames(getattr(self, "list_box", None))
        if not visible:
            self._toast(gettext.gettext("No servers match the current filters."))
            return

        if not self.latencies:
            # Measure first so Sort can put the true fastest at the top
            # ابتدا تست سرعت تا در صورت فعال بودن مرتب‌سازی، سریع‌ترین بالا باشد
            self.auto_cascade_after_test = True
            self._show_cascade_preparing()
            if not self.sort_by_speed_active and hasattr(self, "sort_btn"):
                self.sort_btn.set_active(True)
            else:
                self.trigger_speed_test()
            return

        self._start_cascade_from_visible_list()

    def _start_cascade_from_visible_list(self):
        visible = collect_visible_filenames(getattr(self, "list_box", None))
        queue = build_cascade_queue(visible, self.latencies, skip_unreachable=True)
        if not queue:
            if self._cascade_active:
                self._finish_cascade(CascadePhase.EXHAUSTED)
            else:
                self._toast(gettext.gettext("No reachable servers in the current list."))
            return

        current = self.get_selected_config()
        try:
            already = bool(self.CM().status())
        except Exception:
            already = False
        if already and current == queue[0]:
            if self._cascade_active:
                self._cascade_current = current
                self._finish_cascade(CascadePhase.SUCCEEDED)
            else:
                self._toast(
                    gettext.gettext(
                        "Already connected to the first server in the list: {}"
                    ).format(current)
                )
            return

        if len(visible) > MAX_CASCADE_CANDIDATES:
            self._toast(
                gettext.gettext("Auto-connect will try the first {} of {} visible servers.").format(
                    len(queue), len(visible)
                )
            )

        self._begin_cascade(queue)

    def _show_cascade_preparing(self):
        self._cascade_active = True
        self._cascade_gen += 1
        self._cascade_phase = CascadePhase.PREPARING
        self._cascade_queue = []
        self._cascade_index = 0
        self._cascade_current = None
        if hasattr(self, "cascade_banner"):
            self.cascade_banner.remove_css_class("cascade-success")
            self.cascade_banner.remove_css_class("cascade-fail")
            self.cascade_title.set_text(gettext.gettext("Measuring latency before auto-connect…"))
            self.cascade_meta.set_text("")
            self.cascade_bar.set_fraction(0.0)
            self.cascade_spinner.start()
            self.cascade_revealer.set_reveal_child(True)
        self._set_fastest_button_cancel(True)

    def _begin_cascade(self, queue: list[str]):
        self._cascade_gen += 1
        self._cascade_active = True
        self._cascade_queue = list(queue)
        self._cascade_index = 0
        self._cascade_failures = []
        self._cascade_expect_disconnect = False
        self._cascade_disconnect_retries = 0
        self._cascade_phase = CascadePhase.CONNECTING
        self._cascade_current = None
        self.manual_disconnect = False

        self._set_cascade_controls_locked(True)
        self._set_fastest_button_cancel(True)
        if hasattr(self, "cascade_banner"):
            self.cascade_banner.remove_css_class("cascade-success")
            self.cascade_banner.remove_css_class("cascade-fail")
            self.cascade_spinner.start()
            self.cascade_revealer.set_reveal_child(True)

        self._toast(
            gettext.gettext("Auto-connect started — {} server(s) in the current list.").format(
                len(self._cascade_queue)
            )
        )

        try:
            if self.CM().status():
                self._cascade_expect_disconnect = True
                self.manual_disconnect = True
                self._cascade_phase = CascadePhase.SETTLING
                self._update_cascade_banner(
                    status=gettext.gettext("Disconnecting current session…")
                )
                self.CM().start_watch()
                self.CM().disconnect()
                self._arm_settle(self._try_current_server)
                return
        except Exception as exc:
            logger.error("Cascade pre-disconnect failed: %s", exc)

        self._try_current_server()

    def _try_current_server(self):
        if not self._cascade_active:
            return False
        if self._cascade_index >= len(self._cascade_queue):
            self._finish_cascade(CascadePhase.EXHAUSTED)
            return False

        filename = self._cascade_queue[self._cascade_index]
        self._cascade_current = filename
        self._cascade_phase = CascadePhase.CONNECTING
        rtt = (self.latencies or {}).get(filename)
        timeout = compute_attempt_timeout(rtt)
        self._cascade_deadline = time.monotonic() + timeout
        self._cascade_expect_disconnect = False
        self.manual_disconnect = False

        self._select_server_by_name(filename)
        self._update_cascade_banner()
        self._arm_timeout_and_ticks()

        manager = self.CM()
        try:
            manager.start_watch()
            if manager.status():
                retries = getattr(self, "_cascade_disconnect_retries", 0) + 1
                self._cascade_disconnect_retries = retries
                if retries > 3:
                    logger.warning("Cascade: still connected after disconnect retries")
                    self._advance_cascade("disconnect")
                    return False
                self._cascade_expect_disconnect = True
                self.manual_disconnect = True
                self._cascade_phase = CascadePhase.SETTLING
                manager.disconnect()
                self._arm_settle(self._try_current_server)
                return False
            self._cascade_disconnect_retries = 0
            path = os.path.join(self.EOVPN_CONFIG_DIR, "CONFIGS", filename)
            if not os.path.isfile(path):
                logger.warning("Cascade: missing config %s", path)
                self._advance_cascade("missing")
                return False
            manager.connect(path)
        except Exception as exc:
            logger.error("Cascade connect error for %s: %s", filename, exc)
            self._advance_cascade("error")
        return False

    def _select_server_by_name(self, filename: str) -> bool:
        """Selects a list row by filename and scrolls it into view."""
        rows = self.retrieve(StorageItem.LISTBOX_ROWS) or []
        row = next((r for r in rows if getattr(r, "filename", None) == filename), None)
        if row is None:
            return False
        try:
            self.list_box.select_row(row)
            alloc = row.get_allocation()
            adj = self.scrolled_window.get_vadjustment()
            if adj and alloc:
                adj.set_value(max(0, alloc.y - 24))
        except Exception as exc:
            logger.debug("Could not scroll to %s: %s", filename, exc)
        return True

    def _update_cascade_banner(self, status: str | None = None):
        if not hasattr(self, "cascade_title"):
            return
        total = max(1, len(self._cascade_queue))
        idx = min(self._cascade_index + 1, total)
        name = self._cascade_current or ""
        rtt = (self.latencies or {}).get(name)
        proto = format_proto_badge(self._protocols_for(name)) if name else ""
        remaining = max(0, int(round(self._cascade_deadline - time.monotonic())))

        if status:
            self.cascade_title.set_text(status)
        else:
            extras = [part for part in (proto, f"{rtt} ms" if rtt is not None else "") if part]
            suffix = f"  ·  {' · '.join(extras)}" if extras else ""
            self.cascade_title.set_text(
                gettext.gettext("Trying {}{}").format(name, suffix)
            )
        self.cascade_meta.set_text(
            gettext.gettext("{}/{}  ·  {}s left").format(idx, len(self._cascade_queue) or total, remaining)
        )

        attempt_timeout = compute_attempt_timeout(rtt)
        elapsed = attempt_timeout - max(0.0, self._cascade_deadline - time.monotonic())
        frac_this = min(1.0, max(0.0, elapsed / max(attempt_timeout, 0.001)))
        overall = (self._cascade_index + frac_this) / total
        self.cascade_bar.set_fraction(min(1.0, overall))
        if hasattr(self, "progress_bar") and self._cascade_phase == CascadePhase.CONNECTING:
            self.progress_bar.set_fraction(min(0.92, (self._cascade_index + 0.4) / total))

    def _arm_timeout_and_ticks(self):
        self._disarm_cascade_timers(keep_settle=False)
        remaining_ms = max(250, int((self._cascade_deadline - time.monotonic()) * 1000))
        gen = self._cascade_gen
        self._cascade_timeout_id = GLib.timeout_add(remaining_ms, self._on_cascade_timeout, gen)
        self._cascade_tick_id = GLib.timeout_add(PROGRESS_TICK_MS, self._on_cascade_tick, gen)

    def _disarm_cascade_timers(self, keep_settle: bool = False):
        attrs = ["_cascade_timeout_id", "_cascade_tick_id"]
        if not keep_settle:
            attrs.append("_cascade_settle_id")
        for attr in attrs:
            source_id = getattr(self, attr, None)
            if source_id:
                try:
                    GLib.source_remove(source_id)
                except Exception:
                    pass
                setattr(self, attr, None)

    def _on_cascade_tick(self, gen: int) -> bool:
        if not self._cascade_active or gen != self._cascade_gen:
            return False
        if self._cascade_user_is_busy():
            # Freeze the deadline while an OTP / modal dialog is open
            # توقف شمارش معکوس وقتی دیالوگ OTP یا مودال باز است
            self._cascade_deadline += PROGRESS_TICK_MS / 1000.0
            return True
        self._update_cascade_banner()
        return True

    def _on_cascade_timeout(self, gen: int) -> bool:
        self._cascade_timeout_id = None
        if not self._cascade_active or gen != self._cascade_gen:
            return False
        if self._cascade_user_is_busy():
            self._cascade_deadline = time.monotonic() + 4.0
            self._arm_timeout_and_ticks()
            return False
        try:
            if self.CM().status():
                # Handshake landed in the same tick as the timeout
                # دست‌دهی درست همزمان با اتمام تایم‌اوت موفق شده است
                return False
        except Exception:
            pass
        logger.info("Cascade handshake timeout on %s", self._cascade_current)
        self._advance_cascade("timeout")
        return False

    def _cascade_user_is_busy(self) -> bool:
        """True when a modal dialog (OTP, etc.) is waiting for the user."""
        try:
            for win in self.app.get_windows():
                if win is not self.window and win.get_mapped() and win.get_modal():
                    return True
        except Exception:
            pass
        return False

    def _arm_settle(self, callback):
        if self._cascade_settle_id:
            try:
                GLib.source_remove(self._cascade_settle_id)
            except Exception:
                pass
            self._cascade_settle_id = None
        gen = self._cascade_gen

        def _fire():
            self._cascade_settle_id = None
            if self._cascade_active and gen == self._cascade_gen:
                callback()
            return False

        self._cascade_settle_id = GLib.timeout_add(
            int(DISCONNECT_SETTLE_SECONDS * 1000), _fire
        )

    def _advance_cascade(self, reason: str):
        if not self._cascade_active:
            return
        current = self._cascade_current
        if current:
            self._cascade_failures.append((current, reason))
            logger.info("Cascade skip %s (%s)", current, reason)

        self._disarm_cascade_timers()
        self._toast(
            gettext.gettext("Could not connect to {} ({}) — next server…").format(
                current or "?", self._cascade_reason_label(reason)
            )
        )

        self._cascade_index += 1
        self._cascade_phase = CascadePhase.SETTLING
        self._cascade_expect_disconnect = True
        self.manual_disconnect = True

        try:
            if self.CM().status():
                self.CM().disconnect()
                self._arm_settle(self._try_current_server)
                return
        except Exception as exc:
            logger.debug("Cascade disconnect on advance: %s", exc)

        self._arm_settle(self._try_current_server)

    def _cascade_reason_label(self, reason: str) -> str:
        labels = {
            "timeout": gettext.gettext("timed out"),
            "error": gettext.gettext("error"),
            "auth": gettext.gettext("authentication failed"),
            "disconnect": gettext.gettext("disconnected"),
            "missing": gettext.gettext("file missing"),
            "unreachable": gettext.gettext("unreachable"),
        }
        return labels.get(reason, reason)

    def _cascade_on_connection_event(self, result, error=None) -> bool:
        """
        Consumes D-Bus connection events while a cascade is running.
        Returns True when the regular UI handler must be skipped.
        رویدادهای D-Bus را هنگام اتصال آبشاری مصرف می‌کند.
        """
        if result is True:
            self._disarm_cascade_timers()
            self._cascade_expect_disconnect = False
            self._finish_cascade(CascadePhase.SUCCEEDED, restore_connect_ui=False)
            return False

        error_text = str(error).lower() if error else ""
        failed = result is False or error is not None
        if not failed:
            return False

        if self._cascade_phase == CascadePhase.SETTLING and self._cascade_expect_disconnect:
            self._cascade_expect_disconnect = False
            self.manual_disconnect = True
            return True

        if self._cascade_phase == CascadePhase.CONNECTING:
            reason = "auth" if "auth" in error_text else ("error" if error else "disconnect")
            self._advance_cascade(reason)
            return True

        return True

    def _finish_cascade(self, phase: CascadePhase, restore_connect_ui: bool = True):
        gen_was = self._cascade_gen
        self._disarm_cascade_timers()
        was_preparing = self._cascade_phase == CascadePhase.PREPARING
        self._cascade_active = False
        self._cascade_phase = phase
        self._cascade_expect_disconnect = False
        self.auto_cascade_after_test = False

        self._set_cascade_controls_locked(False)
        self._set_fastest_button_cancel(False)
        if hasattr(self, "cascade_spinner"):
            self.cascade_spinner.stop()

        if phase == CascadePhase.SUCCEEDED:
            name = self._cascade_current or self.get_selected_config() or ""
            rtt = (self.latencies or {}).get(name)
            if rtt is not None:
                msg = gettext.gettext("Connected to {} ({} ms)").format(name, rtt)
            else:
                msg = gettext.gettext("Connected to {}").format(name)
            if hasattr(self, "cascade_title"):
                self.cascade_title.set_text(msg)
                self.cascade_meta.set_text(
                    gettext.gettext("Attempt {}/{}").format(
                        self._cascade_index + 1, max(1, len(self._cascade_queue))
                    )
                )
                self.cascade_banner.add_css_class("cascade-success")
                self.cascade_bar.set_fraction(1.0)
                self.cascade_revealer.set_reveal_child(True)
            self._toast(msg)
            GLib.timeout_add_seconds(3, self._hide_cascade_banner, gen_was)
            return

        if phase == CascadePhase.CANCELLED:
            if hasattr(self, "cascade_revealer"):
                self.cascade_revealer.set_reveal_child(False)
            self._toast(gettext.gettext("Auto-connect cancelled"))
            if restore_connect_ui and not was_preparing:
                try:
                    if self.CM().status():
                        self.manual_disconnect = True
                        self.CM().disconnect()
                except Exception:
                    pass
            return

        n_fail = len(self._cascade_failures)
        if hasattr(self, "cascade_title"):
            self.cascade_title.set_text(
                gettext.gettext("Could not connect to any server in the list")
            )
            self.cascade_meta.set_text(
                gettext.gettext("{} attempt(s) failed").format(n_fail)
            )
            self.cascade_banner.add_css_class("cascade-fail")
            self.cascade_bar.set_fraction(1.0)
            self.cascade_revealer.set_reveal_child(True)
        self._toast(
            gettext.gettext(
                "Auto-connect failed — no server in the current list accepted the handshake."
            ),
            timeout=4,
        )
        GLib.timeout_add_seconds(5, self._hide_cascade_banner, gen_was)

    def _hide_cascade_banner(self, gen: int) -> bool:
        if not self._cascade_active and hasattr(self, "cascade_revealer"):
            self.cascade_revealer.set_reveal_child(False)
            self.cascade_banner.remove_css_class("cascade-success")
            self.cascade_banner.remove_css_class("cascade-fail")
        return False

    def cancel_cascade(self, user: bool = True):
        """Aborts a running cascade or the pre-connect speed test."""
        if not self._cascade_active and not getattr(self, "auto_cascade_after_test", False):
            return
        logger.info("Cascade cancelled (user=%s)", user)
        self.auto_cascade_after_test = False
        self._cascade_gen += 1
        self._finish_cascade(CascadePhase.CANCELLED)

    def _set_fastest_button_cancel(self, cancel: bool):
        if not hasattr(self, "fastest_btn"):
            return
        if cancel:
            self.fastest_btn.set_label(gettext.gettext("Cancel"))
            self.fastest_btn.remove_css_class("suggested-action")
            self.fastest_btn.add_css_class("destructive-action")
            self.fastest_btn.set_tooltip_text(gettext.gettext("Cancel auto-connect"))
        else:
            self.fastest_btn.set_label(gettext.gettext("Connect Fastest"))
            self.fastest_btn.remove_css_class("destructive-action")
            self.fastest_btn.add_css_class("suggested-action")
            self.fastest_btn.set_tooltip_text(gettext.gettext(
                "Connect to the first server in the current sorted and filtered list. "
                "If the handshake times out or fails, automatically try the next one."
            ))

    def _set_cascade_controls_locked(self, locked: bool):
        widgets = [
            getattr(self, "speed_test_btn", None),
            getattr(self, "sort_btn", None),
            getattr(self, "search_entry", None),
            getattr(self, "filter_dropdown", None),
            getattr(self, "proto_dropdown", None),
            getattr(self, "connect_btn", None),
        ]
        for widget in widgets:
            if widget is not None:
                widget.set_sensitive(not locked)

    def _toast(self, message: str, timeout: int = 2):
        if not hasattr(self, "toast_overlay"):
            return
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)

    def start_network_monitor(self):
        """Starts real-time bandwidth monitoring."""
        self.stop_network_monitor()
        self.last_rx = 0
        self.last_tx = 0
        self.last_time = time.time()
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

            now = time.time()
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
        """
        Worker: performs the network lookup off the main thread.
        GTK widgets must never be touched from worker threads; the UI update
        is therefore scheduled back onto the main loop via GLib.idle_add.
        نخ کارگر: استعلام شبکه خارج از نخ اصلی انجام می‌شود. ویجت‌های GTK هرگز
        نباید از نخ‌های فرعی دستکاری شوند؛ به‌روزرسانی رابط از طریق GLib.idle_add
        به نخ اصلی بازگردانده می‌شود.
        """
        try:
            if os.environ.get("FLATPAK_ID") is not None:
                time.sleep(1.25)
            self.lookup.update()
        finally:
            GLib.idle_add(self._apply_ip_lookup)

    def _apply_ip_lookup(self) -> bool:
        """Applies the lookup result on the GTK main thread."""
        try:
            flag = self.retrieve(StorageItem.FLAG)
            if flag is not None:
                flag.set_pixbuf(self.get_country_pixbuf(self.lookup.country_code))
            self.ip_addr.set_label(self.lookup.ip or "0.0.0.0")
        except Exception as e:
            logger.debug("Failed to apply IP lookup result: %s", e)
        self.spinner.stop()
        return False

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
        if getattr(self, "_cascade_active", False):
            if self._cascade_on_connection_event(result, error):
                return

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
                self.set_setting(self.SETTING.LAST_CONNECTED_CURSOR, configs.index(selected_cfg))

            self.swap_pause_btn_signal_resume_to_pause()

            if self.CM().get_name().lower() == "openvpn3":
                if self.CM().config_path is not None:
                    self.pause_resume_btn.set_visible(True)

        else:
            self.stop_network_monitor()
            self.dl_speed_label.set_text("0.0 B/s")
            self.ul_speed_label.set_text("0.0 B/s")
            self.total_traffic_label.set_text("0 B")

            should_reconnect = (
                getattr(self, "was_connected", False)
                and self.get_setting(self.SETTING.AUTO_RECONNECT)
                and not getattr(self, "manual_disconnect", False)
                and not getattr(self, "_cascade_active", False)
            )
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
        self.spinner.start()
        th = threading.Thread(target=self.update_set_ip_flag)
        th.daemon = True
        th.start()


class MainWindowSignals(Base):
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
