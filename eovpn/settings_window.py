"""
eOVPN-Pro Settings & Preferences Window Module
ماژول پنجره تنظیمات و پیکربندی در eOVPN-Pro

Manages user preferences, configuration sources (ZIP/Folder), credentials, and
backend options. File pickers go through ``ui_compat.FilePicker`` so the window
works on both modern (GTK >= 4.10) and older GTK4 runtimes, and backend
versions are read through lightweight ``probe_version()`` classmethods instead
of instantiating whole backends on the UI thread.

مدیریت ترجیحات کاربر، منابع کانفیگ، نام کاربری و کلمه عبور و گزینه‌های بک‌اند.
انتخاب‌گرهای فایل از ``ui_compat.FilePicker`` عبور می‌کنند تا پنجره روی
رانتایم‌های مدرن و قدیمی GTK4 کار کند و نسخه بک‌اندها با classmethodهای سبک
``probe_version()`` به‌جای نمونه‌سازی کامل روی نخ UI خوانده می‌شود.
"""

import gettext
import logging
import os
import shutil

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk, Secret

from .connection_manager import (
    NetworkManager,
    available_backend_names,
    backend_capabilities,
    create_connection_manager,
)
from .eovpn_base import Base, StorageItem
from .reset_backup import create_reset_backup, latest_reset_backup, load_reset_manifest
from .ui_compat import FilePicker, show_alert

logger = logging.getLogger(__name__)


def probe_secret_service() -> bool | None:
    """Read whether Secret Service is reachable without reading credentials."""
    try:
        service = Secret.Service.get_sync(Secret.ServiceFlags.NONE, None)
    except Exception as exc:  # pragma: no cover - depends on the desktop session
        logger.debug("Secret Service probe failed: %s", exc)
        return False
    return service is not None


class SettingsWindow(Base):
    """
    Controller for the settings modal dialog.
    کنترلر پنجره تنظیمات برنامه.
    """

    def __init__(self):
        super().__init__()
        self.signals = SettingsSignals()

        self.builder = Gtk.Builder()
        self.builder.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/settings.ui")
        self.window = self.builder.get_object("settings_window")
        self.window.set_title(gettext.gettext("{} Settings").format(self.APP_NAME))
        self.window.add_css_class("settings-window")

        parent_win = self.retrieve(StorageItem.MAIN_WINDOW)
        if parent_win and isinstance(parent_win, Gtk.Window):
            self.window.set_transient_for(parent_win)
        self.window.set_modal(True)
        self.store(StorageItem.SETTINGS_WINDOW, self.window)
        self.store("settings_window_instance", self)

    def generate_option_row(self, name: str, icon_name: str, switch_state: bool):
        list_box_row = Gtk.ListBoxRow.new()
        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        v_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        v_box.set_hexpand(True)

        label = Gtk.Label.new(name)
        label.set_halign(Gtk.Align.START)
        label.set_xalign(0.0)
        v_box.set_valign(Gtk.Align.CENTER)
        v_box.append(label)

        img = Gtk.Image.new()
        img.set_from_icon_name(icon_name)
        h_box.append(img)
        h_box.append(v_box)

        switch = Gtk.Switch.new()
        switch.set_halign(Gtk.Align.CENTER)
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_state(switch_state)
        switch.set_active(switch_state)

        h_box.append(switch)
        list_box_row.set_child(h_box)
        list_box_row.set_selectable(False)

        return list_box_row, switch

    def setup(self):
        """
        Constructs and wires the full settings UI by delegating to
        focused builder methods (kept small for maintainability).
        ساخت و اتصال رابط کاربری تنظیمات با تفویض به متدهای سازنده
        تخصصی (برای نگهداری‌پذیری، هر بخش کوچک نگه داشته شده است).
        """

        self._build_header()
        self._build_setup_tab()
        self._build_general_tab()
        self._build_backend_tab()
        self._wire_signals()
        # Let the stack use its natural height so short pages (especially
        # Setup) do not reserve a large empty area below their content.
        self.window.set_default_size(620, 400)
        self.window.set_resizable(False)
        self.stack.set_vexpand(False)

    def _build_header(self):
        self.reset_btn = Gtk.Button.new_with_label(gettext.gettext("Reset"))
        self.reset_btn.add_css_class("destructive-action")
        self.header = self.builder.get_object("settings_header_bar")
        self.header.pack_start(self.reset_btn)
        self.restore_btn = Gtk.Button.new_with_label(gettext.gettext("Restore Reset"))
        self.restore_btn.set_tooltip_text(gettext.gettext("Restore the latest local reset backup"))
        self.restore_btn.set_sensitive(latest_reset_backup(self.EOVPN_OVPN_CONFIG_DIR) is not None)
        self.header.pack_start(self.restore_btn)

        self.spinner = Gtk.Spinner()
        self.tick_mark = Gtk.Image()
        self.tick_mark.set_from_icon_name("object-select-symbolic")
        self.tick_mark.set_visible(False)
        self.store("settings_tick", self.tick_mark)

        self.header.pack_end(self.tick_mark)
        self.header.pack_end(self.spinner)

        self.stack = Gtk.Stack.new()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        self.stack_switcher = Gtk.StackSwitcher.new()
        self.stack_switcher.set_stack(self.stack)
        self.header.set_title_widget(self.stack_switcher)

    def _build_setup_tab(self):
        self.main_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        self.main_box.set_valign(Gtk.Align.START)
        self.main_box.add_css_class("m-6")
        self.main_box.add_css_class("settings-page")

        self.pref_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.backend_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.pref_box.add_css_class("settings-page")
        self.backend_box.add_css_class("settings-page")

        self.stack.add_titled(self.main_box, "setup", gettext.gettext("Setup"))
        self.stack.add_titled(self.pref_box, "general", gettext.gettext("General"))
        self.stack.add_titled(self.backend_box, "Backend", gettext.gettext("Backend"))

        # Setup Tab: Configuration Source
        intro = Gtk.Label.new(
            gettext.gettext(
                "Choose a trusted configuration source, validate it, and manage "
                "optional credentials securely."
            )
        )
        intro.set_halign(Gtk.Align.START)
        intro.set_xalign(0.0)
        intro.set_wrap(True)
        intro.add_css_class("settings-intro")
        self.main_box.append(intro)
        label = Gtk.Label.new(gettext.gettext("Configuration Source"))
        label.set_halign(Gtk.Align.START)
        label.add_css_class("bold")
        self.main_box.append(label)

        configuration_source_hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        self.config_source_entry = Gtk.Entry.new()
        if (text := self.get_setting(self.SETTING.REMOTE)) is not None:
            self.config_source_entry.set_text(text)
        else:
            self.config_source_entry.set_placeholder_text("https://example.com/vpn/configs.zip")

        zip_chooser_btn = Gtk.Button.new_from_icon_name("media-zip-symbolic")
        zip_chooser_btn.set_tooltip_text(gettext.gettext("Choose ZIP File"))
        folder_chooser_btn = Gtk.Button.new_from_icon_name("folder-open-symbolic")
        folder_chooser_btn.set_tooltip_text(gettext.gettext("Choose Local Folder"))
        self.config_source_entry.set_hexpand(True)
        configuration_source_hbox.append(self.config_source_entry)
        configuration_source_hbox.append(zip_chooser_btn)
        configuration_source_hbox.append(folder_chooser_btn)

        # Version-tolerant pickers (Gtk.FileDialog on GTK >= 4.10).
        # انتخاب‌گرهای مقاوم به نسخه (Gtk.FileDialog روی GTK 4.10 به بالا).
        zip_filter = Gtk.FileFilter()
        zip_filter.set_name("ZIP")
        zip_filter.add_mime_type("application/zip")
        self.zip_picker = FilePicker(
            self.window,
            Gtk.FileChooserAction.OPEN,
            gettext.gettext("Choose ZIP File"),
            filters=[zip_filter],
        )
        self.zip_picker.set_initial_dir(GLib.get_home_dir())
        self.folder_picker = FilePicker(
            self.window,
            Gtk.FileChooserAction.SELECT_FOLDER,
            gettext.gettext("Choose Local Folder"),
        )
        self.folder_picker.set_initial_dir(GLib.get_home_dir())
        zip_chooser_btn.connect("clicked", lambda btn: self.zip_picker.show())
        folder_chooser_btn.connect("clicked", lambda btn: self.folder_picker.show())

        self.main_box.append(configuration_source_hbox)

        self.revealer = Gtk.Revealer.new()
        self.validate_btn = Gtk.Button.new_with_label(gettext.gettext("Validate & Load"))
        self.validate_btn.add_css_class("suggested-action")
        self.revealer.set_child(self.validate_btn)
        self.main_box.append(self.revealer)
        self.revealer.set_reveal_child(False)

        # Authentication Section
        self.auth_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        ask_auth_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        ask_auth_box.add_css_class("m-4")
        label = Gtk.Label.new(gettext.gettext("Authentication"))
        label.set_halign(Gtk.Align.START)
        label.add_css_class("bold")
        ask_auth_box.append(label)

        self.ask_auth_switch = Gtk.Switch.new()
        self.ask_auth_switch.set_halign(Gtk.Align.END)
        ask_auth_box.append(self.ask_auth_switch)
        self.auth_box.append(ask_auth_box)

        # Username
        username_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        button = Gtk.Button.new_from_icon_name("avatar-default-symbolic")
        button.set_sensitive(False)
        username_box.append(button)
        self.username_entry = Gtk.Entry.new()
        self.username_entry.set_placeholder_text(gettext.gettext("Username / Email"))
        self.username_entry.set_hexpand(True)
        username_box.append(self.username_entry)

        # Password
        password_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        button = Gtk.Button.new_from_icon_name("dialog-password-symbolic")
        button.set_sensitive(False)
        password_box.append(button)
        self.password_entry = Gtk.PasswordEntry.new()
        self.password_entry.set_property("placeholder-text", gettext.gettext("Password"))
        self.password_entry.set_show_peek_icon(True)
        self.password_entry.set_hexpand(True)
        password_box.append(self.password_entry)

        # CA
        ca_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
        ca_box.add_css_class("mb-4")
        button = Gtk.Button.new_from_icon_name("application-certificate-symbolic")
        button.set_sensitive(False)
        ca_box.append(button)
        self.ca_chooser_btn = Gtk.Button.new_with_label("(None)")
        self.ca_chooser_btn.set_hexpand(True)

        ca_filter = Gtk.FileFilter()
        ca_filter.set_name("CA / CRT")
        ca_filter.add_mime_type("application/pkix-cert")
        self.ca_picker = FilePicker(
            self.window,
            Gtk.FileChooserAction.OPEN,
            gettext.gettext("Choose CA / CRT Certificate"),
            filters=[ca_filter],
        )
        self.ca_picker.set_initial_dir(self.EOVPN_OVPN_CONFIG_DIR)
        self.ca_chooser_btn.connect("clicked", lambda btn: self.ca_picker.show())
        ca_box.append(self.ca_chooser_btn)

        self.user_pass_ca_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 4)
        self.user_pass_ca_box.add_css_class("mt-4")
        self.user_pass_ca_box.append(username_box)
        self.user_pass_ca_box.append(password_box)
        self.user_pass_ca_box.append(ca_box)
        self.user_pass_ca_box.set_sensitive(False)
        self.auth_box.append(self.user_pass_ca_box)
        self.main_box.append(self.auth_box)

        if (auth_status_opt := self.get_setting(self.SETTING.REQ_AUTH)) is not None:
            self.ask_auth_switch.set_state(auth_status_opt)
            self.ask_auth_switch.set_active(auth_status_opt)
            self.user_pass_ca_box.set_sensitive(auth_status_opt)

            if (username := self.get_setting(self.SETTING.AUTH_USER)) is not None:
                self.username_entry.set_text(username)

                def on_password_lookup(source, result):
                    try:
                        pwd = Secret.password_lookup_finish(result)
                    except Exception:
                        pwd = self.get_session_password()

                    if pwd:
                        self.password_entry.set_text(pwd)

                Secret.password_lookup(
                    self.EOVPN_SECRET_SCHEMA, {"username": username}, None, on_password_lookup
                )

            if (ca := self.get_setting(self.SETTING.CA)) is not None:
                self.ca_chooser_btn.set_label(os.path.basename(ca))

    def _build_general_tab(self):
        # General Preferences Tab
        info = Gtk.Label.new(
            gettext.gettext(
                "General preferences apply immediately. Language changes are applied safely after restart."
            )
        )
        info.set_halign(Gtk.Align.START)
        info.set_xalign(0.0)
        info.set_wrap(True)
        info.set_margin_start(12)
        info.set_margin_end(12)
        info.set_margin_top(8)
        info.set_margin_bottom(4)
        info.add_css_class("dim-label")
        self.pref_box.append(info)

        frame = Gtk.Frame.new()
        frame.add_css_class("settings-card")
        list_box = Gtk.ListBox.new()
        frame.add_css_class("m-10")
        list_box.add_css_class("rich-list")

        self.switches = [self.ask_auth_switch]

        row, switch = self.generate_option_row(
            gettext.gettext("Notifications"),
            "user-available-symbolic",
            bool(self.get_setting(self.SETTING.NOTIFICATIONS)),
        )
        switch.connect("state-set", self.signals.notification_set)
        self.switches.append(switch)
        list_box.append(row)

        row, switch = self.generate_option_row(
            gettext.gettext("Flag"),
            "preferences-desktop-locale-symbolic",
            bool(self.get_setting(self.SETTING.SHOW_FLAG)),
        )
        switch.connect("state-set", self.signals.show_flag_set)
        self.switches.append(switch)
        list_box.append(row)

        row, switch = self.generate_option_row(
            gettext.gettext("Dark Theme"),
            "weather-clear-night-symbolic",
            bool(self.get_setting(self.SETTING.DARK_THEME)),
        )
        switch.connect("state-set", self.signals.dark_theme_set)
        self.switches.append(switch)
        list_box.append(row)

        row, switch = self.generate_option_row(
            gettext.gettext("Auto Reconnect"),
            "network-wired-symbolic",
            bool(self.get_setting(self.SETTING.AUTO_RECONNECT)),
        )
        switch.connect("state-set", self.signals.auto_reconnect_set)
        self.switches.append(switch)
        list_box.append(row)

        frame.set_child(list_box)
        self.pref_box.append(frame)

        # The native backend removes only profiles identified as created by
        # eOVPN-Pro; the label must not imply a system-wide wipe.
        # بک‌اند بومی فقط پروفایل‌های دارای برچسب `managed-by=eovpn-pro` را حذف
        # می‌کند (تابع eovpn_connection_is_managed در فایل eovpn_nm.c)، بنابراین
        # برچسب دکمه نباید پاک‌سازی سراسری سیستم را القا کند.
        self.remove_all_vpn_btn = Gtk.Button.new_with_label(gettext.gettext("Delete All eOVPN-Pro Profiles"))
        self.remove_all_vpn_btn.set_tooltip_text(
            gettext.gettext(
                "Removes every VPN profile created by eOVPN-Pro from NetworkManager. "
                "Profiles added by other applications are left untouched."
            )
        )
        self.remove_all_vpn_btn.add_css_class("m-6")
        self.remove_all_vpn_btn.add_css_class("destructive-action")
        self.remove_all_vpn_btn.set_valign(Gtk.Align.END)
        self.remove_all_vpn_btn.set_vexpand(True)
        self.pref_box.append(self.remove_all_vpn_btn)
        self.remove_all_vpn_btn.set_visible(self.get_setting(self.SETTING.MANAGER) == "networkmanager")
        self.pref_box.set_vexpand(True)
        self.window.set_child(self.stack)

    def _build_backend_tab(self):
        # Backend Tab
        self.backend_box.set_valign(Gtk.Align.START)
        backend_frame = Gtk.Frame.new()
        backend_frame.add_css_class("settings-card")
        backend_list_box = Gtk.ListBox.new()
        backend_frame.add_css_class("m-10")
        backend_list_box.add_css_class("rich-list")

        capabilities = backend_capabilities()

        # Row 1: Connection Backend selection
        row1 = Gtk.ListBoxRow.new()
        row1.set_selectable(False)
        h_box1 = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 12)
        h_box1.set_margin_top(8)
        h_box1.set_margin_bottom(8)
        h_box1.set_margin_start(10)
        h_box1.set_margin_end(10)

        icon1 = Gtk.Image.new_from_icon_name("network-wired-symbolic")
        v_box1 = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        v_box1.set_hexpand(True)
        v_box1.set_valign(Gtk.Align.CENTER)
        label1 = Gtk.Label.new(gettext.gettext("Connection Backend"))
        label1.set_halign(Gtk.Align.START)
        label1.add_css_class("bold")
        v_box1.append(label1)

        self.combobox = Gtk.ComboBoxText()
        self.combobox.set_valign(Gtk.Align.CENTER)
        manager = self.get_setting(self.SETTING.MANAGER) or "networkmanager"
        manager_available = manager in available_backend_names()

        version = capabilities["networkmanager"]["version"]
        ovpn3_version = capabilities["openvpn3"]["version"]
        if version:
            self.combobox.append("networkmanager", gettext.gettext("{} (OpenVPN 2)").format(version))
        if ovpn3_version:
            self.combobox.append("openvpn3", gettext.gettext("OpenVPN 3 {}").format(ovpn3_version))

        if manager_available:
            self.combobox.set_property("active-id", manager)
        else:
            # Never silently replace a persisted backend with another one.
            # The user must explicitly choose an available backend.
            self.combobox.set_active(-1)

        h_box1.append(icon1)
        h_box1.append(v_box1)
        h_box1.append(self.combobox)
        row1.set_child(h_box1)
        backend_list_box.append(row1)

        backend_status = Gtk.Label.new()
        backend_status.set_halign(Gtk.Align.START)
        backend_status.set_xalign(0.0)
        backend_status.set_wrap(True)
        backend_status.set_margin_start(10)
        backend_status.set_margin_end(10)
        backend_status.set_margin_top(4)
        backend_status.set_margin_bottom(8)
        backend_status.add_css_class("dim-label")
        status_lines = []
        if version:
            status_lines.append(gettext.gettext("NetworkManager: Ready ({})").format(version))
        else:
            status_lines.append(gettext.gettext("NetworkManager: Unavailable"))
        plugin = capabilities["networkmanager"]["openvpn_plugin"]
        if plugin is True:
            status_lines.append(gettext.gettext("NetworkManager OpenVPN plugin: Ready"))
        elif plugin is False:
            status_lines.append(gettext.gettext("NetworkManager OpenVPN plugin: Missing"))
        else:
            status_lines.append(gettext.gettext("NetworkManager OpenVPN plugin: Unknown"))
        if ovpn3_version:
            status_lines.append(gettext.gettext("OpenVPN 3: Available ({})").format(ovpn3_version))
        else:
            status_lines.append(gettext.gettext("OpenVPN 3: Unavailable (optional binding is not installed)"))
        available = available_backend_names()
        status_lines.append(
            gettext.gettext("NetworkManager native bindings: {}").format(
                gettext.gettext("Ready") if "networkmanager" in available else gettext.gettext("Unavailable")
            )
        )
        cffi_state = str(capabilities["networkmanager"].get("cffi_contract", "unknown"))
        cffi_label = {
            "current": gettext.gettext("Current"),
            "legacy": gettext.gettext("Legacy; rebuild required"),
            "unavailable": gettext.gettext("Unavailable"),
        }.get(cffi_state, gettext.gettext("Unknown"))
        status_lines.append(gettext.gettext("NetworkManager CFFI: {}").format(cffi_label))
        status_lines.append(
            gettext.gettext("DCO: Available with OpenVPN 3")
            if capabilities["openvpn3"]["dco"]
            else gettext.gettext("DCO: Unavailable because OpenVPN 3 is unavailable")
        )
        language = self.get_setting(self.SETTING.LANGUAGE) or "en"
        theme = (
            gettext.gettext("Dark")
            if self.get_setting(self.SETTING.DARK_THEME)
            else gettext.gettext("System")
        )
        status_lines.append(gettext.gettext("Language: {} · Theme: {}").format(language, theme))
        secret_service = probe_secret_service()
        status_lines.append(
            gettext.gettext("Secret Service: {}").format(
                gettext.gettext("Available") if secret_service else gettext.gettext("Unavailable")
            )
        )
        backend_status.set_text("\n".join(status_lines))
        status_row = Gtk.ListBoxRow.new()
        status_row.set_selectable(False)
        status_row.set_child(backend_status)
        backend_list_box.append(status_row)

        # Row 2: OpenVPN 3 DCO
        self.dco_row = Gtk.ListBoxRow.new()
        self.dco_row.set_selectable(False)
        h_box2 = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 12)
        h_box2.set_margin_top(8)
        h_box2.set_margin_bottom(8)
        h_box2.set_margin_start(10)
        h_box2.set_margin_end(10)

        icon2 = Gtk.Image.new_from_icon_name("speedometer-symbolic")
        v_box2 = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        v_box2.set_hexpand(True)
        v_box2.set_valign(Gtk.Align.CENTER)

        label2 = Gtk.Label.new(gettext.gettext("Data Channel Offload (DCO)"))
        label2.set_halign(Gtk.Align.START)
        label2.add_css_class("bold")

        sub_label2 = Gtk.Label.new(
            gettext.gettext(
                "Offloads VPN data processing directly to the Linux kernel "
                "for maximum speed and lower CPU usage."
            )
        )
        sub_label2.set_halign(Gtk.Align.START)
        sub_label2.add_css_class("dim-label")
        sub_label2.add_css_class("caption")
        sub_label2.set_wrap(True)
        sub_label2.set_max_width_chars(45)

        v_box2.append(label2)
        v_box2.append(sub_label2)

        self.dco_switch = Gtk.Switch.new()
        self.dco_switch.set_halign(Gtk.Align.CENTER)
        self.dco_switch.set_valign(Gtk.Align.CENTER)
        dco_state = bool(self.get_setting(self.SETTING.OPENVPN3_DCO))
        self.dco_switch.set_state(dco_state)
        self.dco_switch.set_active(dco_state)
        dco_available = bool(capabilities["openvpn3"]["dco"])
        self.dco_switch.set_sensitive(dco_available)
        if not dco_available:
            self.dco_switch.set_tooltip_text(
                gettext.gettext("Install the optional OpenVPN 3 backend to enable DCO.")
            )

        h_box2.append(icon2)
        h_box2.append(v_box2)
        h_box2.append(self.dco_switch)
        self.dco_row.set_child(h_box2)
        backend_list_box.append(self.dco_row)

        backend_frame.set_child(backend_list_box)
        self.backend_box.append(backend_frame)

        self.dco_row.set_visible(manager_available and manager == "openvpn3")
        self.dco_switch.connect("state-set", self.signals.openvpn3_dco_set)

    def _wire_signals(self):
        # Connect signals
        self.reset_btn.connect(
            "clicked",
            self.signals.on_reset_btn_clicked,
            [self.config_source_entry, self.username_entry, self.password_entry],
            [self.ca_chooser_btn],
            self.switches,
            self.window,
            self.restore_btn,
        )
        self.restore_btn.connect(
            "clicked",
            self.signals.on_restore_btn_clicked,
            [self.config_source_entry, self.username_entry, self.password_entry],
            [self.ca_chooser_btn],
            self.switches,
            self.window,
            self.restore_btn,
        )
        self.config_source_entry.connect("changed", self.signals.process_config_entry, self.revealer)
        self.zip_picker.connect_picked(
            lambda path: self.signals.process_source_picked(path, self.config_source_entry, self.revealer)
        )
        self.folder_picker.connect_picked(
            lambda path: self.signals.process_source_picked(path, self.config_source_entry, self.revealer)
        )
        self.validate_btn.connect(
            "clicked",
            self.signals.on_validate_btn_click,
            self.config_source_entry,
            self.ca_chooser_btn,
            self.spinner,
        )
        self.username_entry.connect("changed", self.signals.process_username)
        self.password_entry.connect("changed", self.signals.process_password)
        self.ca_picker.connect_picked(lambda path: self.signals.process_ca_picked(path, self.ca_chooser_btn))
        self.ask_auth_switch.connect("state-set", self.signals.req_auth, self.user_pass_ca_box)
        self.remove_all_vpn_btn.connect("clicked", self.confirm_delete_all_connections)
        self.combobox.connect("changed", self.signals.on_backend_selected)

    def confirm_delete_all_connections(self, button: Gtk.Button):
        """
        Asks for explicit confirmation before removing the VPN profiles that
        eOVPN-Pro itself created in NetworkManager.

        The scope is deliberately narrow: ``delete_all_vpn_connections()`` in
        the native backend iterates the NetworkManager profile list and skips
        every connection that is not tagged ``managed-by=eovpn-pro``. Profiles
        belonging to other applications are therefore never touched, and the
        confirmation text states exactly that so the user is not warned about
        damage the code cannot cause. The action is still irreversible for our
        own profiles.

        درخواست تأیید صریح پیش از حذف پروفایل‌های VPN که خودِ eOVPN-Pro در
        NetworkManager ساخته است.

        دامنهٔ عملیات عمداً محدود است: تابع `delete_all_vpn_connections()` در
        بک‌اند بومی فهرست پروفایل‌های NetworkManager را پیمایش می‌کند و از هر
        اتصالی که برچسب `managed-by=eovpn-pro` ندارد عبور می‌کند. بنابراین
        پروفایل‌های سایر برنامه‌ها هرگز دست‌کاری نمی‌شوند و متن تأیید دقیقاً همین
        را بیان می‌کند تا کاربر دربارهٔ خسارتی که کد اصلاً توان ایجادش را ندارد
        هشدار نگیرد. با این حال این عمل برای پروفایل‌های خودِ ما بازگشت‌ناپذیر است.
        """
        show_alert(
            self.window,
            gettext.gettext("Delete all eOVPN-Pro profiles?"),
            gettext.gettext(
                "Every VPN profile that eOVPN-Pro created in NetworkManager will be "
                "permanently removed. VPN profiles added by other applications are "
                "not affected. This action cannot be undone."
            ),
            [gettext.gettext("Cancel"), gettext.gettext("Delete Profiles")],
            # Cancel is also the default so that Enter or Escape never destroys data.
            # «انصراف» دکمهٔ پیش‌فرض هم هست تا فشردن Enter یا Escape هرگز داده‌ای را
            # از بین نبرد.
            cancel_index=0,
            default_index=0,
            on_response=self._on_delete_all_response,
        )

    def _on_delete_all_response(self, index: int) -> None:
        """
        Deletes the managed profiles only when the destructive button was chosen.
        فقط در صورتی که دکمهٔ مخرب انتخاب شده باشد، پروفایل‌های مدیریت‌شده را حذف می‌کند.
        """
        if index != 1:
            logger.debug("Delete-all dismissed without confirmation.")
            return
        try:
            NetworkManager(None).delete_all_connections()
            logger.info("eOVPN-Pro managed VPN profiles were deleted by user confirmation.")
        except Exception as e:
            logger.error("Delete-all confirmation failed: %s", e)

    def show(self):
        self.setup()
        self.window.set_visible(True)


class SettingsSignals(Base):
    """
    Signals handler for settings UI actions.
    مدیریت سیگنال‌ها و رویدادهای پنجره تنظیمات.
    """

    #: Idle time (ms) after the last keystroke before the password is persisted.
    #: مدت بی‌کاری (میلی‌ثانیه) پس از آخرین کلید، پیش از ماندگار کردن رمز.
    _KEYRING_DEBOUNCE_MS = 800

    def __init__(self):
        super().__init__()
        # GLib source id of the pending keyring write, or None.
        # شناسهٔ منبع GLib برای نوشتن معلق در جاکلیدی، یا None.
        self._keyring_write_source: int | None = None

    def process_config_entry(self, entry, revealer):
        text = entry.get_text()
        if text:
            self.set_setting(self.SETTING.REMOTE, text)
            revealer.set_reveal_child(True)
        else:
            self.set_setting(self.SETTING.REMOTE, None)
            revealer.set_reveal_child(False)

    def process_source_picked(self, path, entry, revealer):
        """Handles a picked ZIP file or local folder path."""
        if not path:
            return
        eb = Gtk.EntryBuffer()
        eb.set_text(path, len(path))
        self.set_setting(self.SETTING.REMOTE, path)
        entry.set_buffer(eb)
        revealer.set_reveal_child(True)

    def req_auth(self, switch, state, auth_box):
        self.set_setting(self.SETTING.REQ_AUTH, state)
        auth_box.set_sensitive(state)

    def process_username(self, entry):
        text = entry.get_text()
        self.set_setting(self.SETTING.AUTH_USER, text if text else None)

    def process_password(self, entry):
        """
        Caches the typed password in RAM and schedules a debounced keyring write.

        The ``changed`` signal fires on every keystroke. Writing to the Secret
        Service that often would emit one D-Bus round-trip per character,
        leaving a trail of partial passwords in the keyring journal and, on
        some keyring back-ends, triggering an unlock prompt storm. The
        in-memory session cache is still updated immediately (it is cheap and
        the connection path reads it), while the persistent write is deferred
        until the user has paused typing for ``_KEYRING_DEBOUNCE_MS``.

        رمز واردشده را در حافظه ذخیره می‌کند و نوشتن در جاکلیدی را با تأخیر
        زمان‌بندی می‌کند.

        سیگنال `changed` با هر بار فشردن کلید فعال می‌شود. نوشتن با این تناوب در
        Secret Service به‌ازای هر کاراکتر یک رفت‌وبرگشت D-Bus ایجاد می‌کند، ردی از
        رمزهای ناقص در ژورنال جاکلیدی باقی می‌گذارد و در برخی پیاده‌سازی‌ها موجب
        سیل درخواست‌های باز کردن قفل می‌شود. حافظهٔ نشست بی‌درنگ به‌روزرسانی می‌شود
        (کم‌هزینه است و مسیر اتصال از آن می‌خواند) اما نوشتن ماندگار تا زمانی که
        کاربر به‌اندازهٔ `_KEYRING_DEBOUNCE_MS` تایپ را متوقف کند به تعویق می‌افتد.
        """
        pwd = entry.get_text()
        username = self.get_setting(self.SETTING.AUTH_USER)

        # Any new keystroke invalidates a pending write.
        # هر کلید جدید، نوشتن معلق قبلی را باطل می‌کند.
        self._cancel_pending_keyring_write()

        if pwd and username:
            # Store in volatile RAM session cache
            # ذخیره در حافظه موقت پروسس
            self.set_session_password(pwd)
            self._keyring_write_source = GLib.timeout_add(
                self._KEYRING_DEBOUNCE_MS,
                self._flush_password_to_keyring,
                username,
                pwd,
            )
        else:
            self.set_session_password(None)

    def _cancel_pending_keyring_write(self) -> None:
        """
        Drops a scheduled keyring write, if one is still queued.
        در صورت وجود، نوشتن زمان‌بندی‌شده در جاکلیدی را لغو می‌کند.
        """
        if self._keyring_write_source is not None:
            GLib.source_remove(self._keyring_write_source)
            self._keyring_write_source = None

    def _flush_password_to_keyring(self, username: str, pwd: str) -> bool:
        """
        Performs the actual asynchronous Secret Service write.

        Returns ``GLib.SOURCE_REMOVE`` so the timeout fires exactly once.
        A failure here is not fatal: the password remains in the session cache
        for the lifetime of the process, which is what a keyring-less system
        (or a locked collection) falls back to anyway.

        نوشتن واقعی و ناهمگام در Secret Service را انجام می‌دهد.

        مقدار `GLib.SOURCE_REMOVE` را برمی‌گرداند تا تایمر فقط یک بار اجرا شود.
        شکست در این مرحله بحرانی نیست: رمز تا پایان عمر پروسه در حافظهٔ نشست
        باقی می‌ماند و همان چیزی است که سیستم فاقد جاکلیدی (یا مجموعهٔ قفل‌شده)
        به آن بازمی‌گردد.
        """
        self._keyring_write_source = None

        def on_password_stored(source, result):
            try:
                Secret.password_store_finish(result)
                logger.debug("Password stored securely in Secret Service.")
            except Exception as e:
                logger.info("Secret service unavailable, retained in memory session: %s", e)

        attributes = {"username": username}
        Secret.password_store(
            self.EOVPN_SECRET_SCHEMA,
            attributes,
            Secret.COLLECTION_DEFAULT,
            "eOVPN Password",
            pwd,
            None,
            on_password_stored,
        )
        return GLib.SOURCE_REMOVE

    def process_ca_picked(self, path, button):
        """Stores the picked CA certificate path."""
        if not path:
            return
        self.set_setting(self.SETTING.CA, path)
        button.set_label(Gio.File.new_for_path(path).get_basename())

    def notification_set(self, switch, state):
        self.set_setting(self.SETTING.NOTIFICATIONS, state)

    def show_flag_set(self, switch, state):
        self.set_setting(self.SETTING.SHOW_FLAG, state)
        flag_img = self.retrieve(StorageItem.FLAG)
        if flag_img:
            flag_img.set_visible(bool(state))

    def dark_theme_set(self, switch, state):
        gtk_settings = Gtk.Settings().get_default()
        self.set_setting(self.SETTING.DARK_THEME, state)
        if gtk_settings:
            gtk_settings.set_property("gtk-application-prefer-dark-theme", state)

    def auto_reconnect_set(self, switch, state):
        self.set_setting(self.SETTING.AUTO_RECONNECT, state)

    def on_reset_btn_clicked(self, button, entries, buttons, switches, window, restore_button):
        show_alert(
            window,
            gettext.gettext("Reset eOVPN-Pro settings and configurations?"),
            gettext.gettext(
                "This clears saved preferences, credentials, and imported VPN configurations. "
                "A local backup of non-secret settings and imported configurations will be kept "
                "so the latest reset can be restored."
            ),
            [gettext.gettext("Cancel"), gettext.gettext("Reset Everything")],
            cancel_index=0,
            default_index=0,
            on_response=lambda index: self._apply_reset(
                index, entries, buttons, switches, window, restore_button
            ),
        )

    def _apply_reset(self, index, entries, buttons, switches, window, restore_button):
        """Apply a confirmed reset only after creating a local rollback snapshot."""
        if index != 1:
            logger.debug("Reset dismissed without confirmation.")
            return
        settings = {key: self.get_setting(key) for key in self.SETTING.all_settings}
        try:
            backup_path = create_reset_backup(self.EOVPN_OVPN_CONFIG_DIR, settings)
        except Exception as exc:
            logger.exception("Could not create reset backup")
            show_alert(
                window,
                gettext.gettext("Reset was not performed"),
                gettext.gettext("A safe local backup could not be created: {}").format(exc),
                [gettext.gettext("Close")],
            )
            return
        self._clear_persisted_password(settings.get(self.SETTING.AUTH_USER))
        self.reset_all_settings()
        self.set_session_password(None)
        self.reset_paths()

        for e in entries:
            e.set_text("")
        for b in buttons:
            b.set_label("(None)")
        for s in switches:
            s.set_state(False)

        GLib.idle_add(self.remove_only, False)
        flag_img = self.retrieve(StorageItem.FLAG)
        if flag_img:
            flag_img.set_visible(False)
        restore_button.set_sensitive(True)
        show_alert(
            window,
            gettext.gettext("Reset completed"),
            gettext.gettext("A local backup was kept at {}. Use Restore Reset to undo this reset.").format(
                backup_path
            ),
            [gettext.gettext("Close")],
        )

    def on_restore_btn_clicked(self, button, entries, buttons, switches, window, restore_button):
        backup = latest_reset_backup(self.EOVPN_OVPN_CONFIG_DIR)
        if backup is None:
            restore_button.set_sensitive(False)
            return
        show_alert(
            window,
            gettext.gettext("Restore the latest reset?"),
            gettext.gettext(
                "Current non-secret settings and imported configurations will first be backed up, "
                "then the latest reset snapshot will be restored."
            ),
            [gettext.gettext("Cancel"), gettext.gettext("Restore")],
            cancel_index=0,
            default_index=0,
            on_response=lambda index: self._apply_restore(
                index, backup, entries, buttons, switches, window, restore_button
            ),
        )

    def _apply_restore(self, index, backup, entries, buttons, switches, window, restore_button):
        """Restore a validated snapshot after explicit confirmation."""
        if index != 1:
            logger.debug("Restore dismissed without confirmation.")
            return
        current_settings = {key: self.get_setting(key) for key in self.SETTING.all_settings}
        try:
            safety_backup = create_reset_backup(self.EOVPN_OVPN_CONFIG_DIR, current_settings)
            manifest = load_reset_manifest(str(backup), self.EOVPN_OVPN_CONFIG_DIR)
            source = backup / "config"
            if source.exists() and source.is_symlink():
                raise ValueError("reset snapshot config is a symlink")
            self._clear_persisted_password(current_settings.get(self.SETTING.AUTH_USER))
            self.reset_paths()
            if source.is_dir():
                shutil.copytree(source, self.EOVPN_OVPN_CONFIG_DIR, symlinks=True, dirs_exist_ok=True)
            self.reset_all_settings()
            for key, value in manifest["settings"].items():
                if key in self.SETTING.all_settings:
                    self.set_setting(key, value)
            self.set_session_password(None)
        except Exception as exc:
            logger.exception("Could not restore reset backup")
            show_alert(
                window,
                gettext.gettext("Restore was not completed"),
                gettext.gettext("The current state was preserved in {}. Details: {}").format(
                    safety_backup, exc
                ),
                [gettext.gettext("Close")],
            )
            return

        self._refresh_controls_after_restore(entries, buttons, switches)
        GLib.idle_add(self.remove_only, False)
        GLib.idle_add(self.load_only)
        restore_button.set_sensitive(latest_reset_backup(self.EOVPN_OVPN_CONFIG_DIR) is not None)
        show_alert(
            window,
            gettext.gettext("Reset restored"),
            gettext.gettext("The previous state was restored. A safety backup was kept at {}.").format(
                safety_backup
            ),
            [gettext.gettext("Close")],
        )

    def _refresh_controls_after_restore(self, entries, buttons, switches):
        """Rebind restored non-secret settings without restoring a password."""
        if entries:
            entries[0].set_text(self.get_setting(self.SETTING.REMOTE) or "")
        if len(entries) > 1:
            entries[1].set_text(self.get_setting(self.SETTING.AUTH_USER) or "")
        if len(entries) > 2:
            entries[2].set_text("")
        if buttons:
            ca_path = self.get_setting(self.SETTING.CA)
            buttons[0].set_label(os.path.basename(ca_path) if ca_path else "(None)")
        setting_keys = (
            self.SETTING.REQ_AUTH,
            self.SETTING.NOTIFICATIONS,
            self.SETTING.SHOW_FLAG,
            self.SETTING.DARK_THEME,
            self.SETTING.AUTO_RECONNECT,
        )
        for switch, key in zip(switches, setting_keys):
            switch.set_state(bool(self.get_setting(key)))
        flag_img = self.retrieve(StorageItem.FLAG)
        if flag_img:
            flag_img.set_visible(bool(self.get_setting(self.SETTING.SHOW_FLAG)))

    def _clear_persisted_password(self, username):
        """Remove the matching Secret Service item without logging its value."""
        if not username:
            return

        def on_cleared(_source, result):
            try:
                Secret.password_clear_finish(result)
                logger.info("Stored VPN credential cleared for the reset user.")
            except Exception as exc:
                logger.warning("Could not clear the stored VPN credential: %s", exc)

        try:
            Secret.password_clear(self.EOVPN_SECRET_SCHEMA, {"username": username}, None, on_cleared)
        except Exception as exc:
            logger.warning("Could not start Secret Service credential cleanup: %s", exc)

    def openvpn3_dco_set(self, switch, state):
        self.set_setting(self.SETTING.OPENVPN3_DCO, state)

    def on_backend_selected(self, box):
        backend_id = box.get_property("active_id")
        if not backend_id:
            return

        callback = self.retrieve("on_connection_event")
        old_record = self.retrieve("CM") or {}
        old_instance = old_record.get("instance")
        stop_old = getattr(old_instance, "stop_watch", None)
        if callable(stop_old):
            try:
                stop_old()
            except Exception as exc:
                logger.debug("Could not stop old backend watcher: %s", exc)

        try:
            instance = create_connection_manager(callback, backend_id)
            if instance.get_name() != backend_id:
                raise RuntimeError(f"{backend_id} backend is not available")
        except Exception as exc:
            logger.error("Requested backend %s unavailable: %s", backend_id, exc)
            self.set_setting(self.SETTING.MANAGER, old_record.get("name", "networkmanager"))
            box.set_property("active-id", old_record.get("name", "networkmanager"))
            return

        self.set_setting(self.SETTING.MANAGER, backend_id)
        self.store("CM", {"name": backend_id, "instance": instance})
        try:
            sw = self.retrieve("settings_window_instance")
            if hasattr(sw, "dco_row"):
                sw.dco_row.set_visible(backend_id == "openvpn3")
        except Exception as e:
            logger.error("Error updating DCO visibility: %s", e)

    def on_validate_btn_click(self, button, entry, ca_button, spinner):
        self.validate_and_load(spinner, ca_button)
