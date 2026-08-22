"""
eOVPN-Pro Settings & Preferences Window Module
ماژول پنجره تنظیمات و پیکربندی در eOVPN-Pro

Manages user preferences, configuration sources (ZIP/Folder), credentials, and backend options.
مدیریت ترجیحات کاربر، منابع کانفیگ، نام کاربری و کلمه عبور و گزینه‌های بک‌اند.
"""

import contextlib
import gettext
import logging
import os
import shutil

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk, Secret

from .connection_manager import NetworkManager, OpenVPN3, create_connection_manager
from .eovpn_base import Base, StorageItem

logger = logging.getLogger(__name__)


class SettingsWindow(Base, Gtk.Builder):
    """
    Controller for the settings modal dialog.
    کنترلر پنجره تنظیمات برنامه.
    """

    def __init__(self):
        super().__init__()
        Gtk.Builder.__init__(self)
        self.signals = SettingsSignals()

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + "settings.ui")
        self.window = self.get_object("settings_window")
        self.window.set_title(gettext.gettext("{} Settings").format(self.APP_NAME))

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

    def _build_header(self):
        self.reset_btn = Gtk.Button.new_with_label(gettext.gettext("Reset"))
        self.reset_btn.add_css_class("destructive-action")
        self.header = self.get_object("settings_header_bar")
        self.header.pack_start(self.reset_btn)

        self.spinner = Gtk.Spinner()
        self.tick_mark = Gtk.Image()
        self.tick_mark.set_from_icon_name("object-select-symbolic")
        self.tick_mark.hide()
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
        self.main_box.set_valign(Gtk.Align.CENTER)
        self.main_box.add_css_class("m-6")

        self.pref_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.backend_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        self.stack.add_titled(self.main_box, "setup", gettext.gettext("Setup"))
        self.stack.add_titled(self.pref_box, "general", gettext.gettext("General"))
        self.stack.add_titled(self.backend_box, "Backend", gettext.gettext("Backend"))

        # Setup Tab: Configuration Source
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

        self.zip_file_chooser_dialog = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
        self.zip_file_chooser_dialog.set_transient_for(self.window)
        zip_filter = Gtk.FileFilter()
        zip_filter.set_name("ZIP")
        zip_filter.add_mime_type("application/zip")
        self.zip_file_chooser_dialog.add_filter(zip_filter)
        default_path = Gio.File.new_for_path(GLib.get_home_dir())
        self.zip_file_chooser_dialog.set_current_folder(default_path)
        zip_chooser_btn.connect("clicked", lambda btn: self.zip_file_chooser_dialog.show())

        self.folder_file_chooser_dialog = Gtk.FileChooserNative(action=Gtk.FileChooserAction.SELECT_FOLDER)
        self.folder_file_chooser_dialog.set_transient_for(self.window)
        self.folder_file_chooser_dialog.set_current_folder(default_path)
        folder_chooser_btn.connect("clicked", lambda btn: self.folder_file_chooser_dialog.show())

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

        self.ca_file_chooser_dialog = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
        self.ca_file_chooser_dialog.set_transient_for(self.window)
        ca_filter = Gtk.FileFilter()
        ca_filter.set_name("CA / CRT")
        ca_filter.add_mime_type("application/pkix-cert")
        self.ca_file_chooser_dialog.add_filter(ca_filter)
        default_path = Gio.File.new_for_path(self.EOVPN_OVPN_CONFIG_DIR)
        self.ca_file_chooser_dialog.set_current_folder(default_path)
        self.ca_chooser_btn.connect("clicked", lambda btn: self.ca_file_chooser_dialog.show())
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
        frame = Gtk.Frame.new()
        list_box = Gtk.ListBox.new()
        frame.add_css_class("m-10")
        list_box.add_css_class("rich-list")

        self.switches = [self.ask_auth_switch]

        row, switch = self.generate_option_row(
            gettext.gettext("Notifications"), "user-available-symbolic",
            bool(self.get_setting(self.SETTING.NOTIFICATIONS))
        )
        switch.connect("state-set", self.signals.notification_set)
        self.switches.append(switch)
        list_box.append(row)

        row, switch = self.generate_option_row(
            gettext.gettext("Flag"), "preferences-desktop-locale-symbolic",
            bool(self.get_setting(self.SETTING.SHOW_FLAG))
        )
        switch.connect("state-set", self.signals.show_flag_set)
        self.switches.append(switch)
        list_box.append(row)

        row, switch = self.generate_option_row(
            gettext.gettext("Dark Theme"), "weather-clear-night-symbolic",
            bool(self.get_setting(self.SETTING.DARK_THEME))
        )
        switch.connect("state-set", self.signals.dark_theme_set)
        self.switches.append(switch)
        list_box.append(row)

        row, switch = self.generate_option_row(
            gettext.gettext("Auto Reconnect"), "network-wired-symbolic",
            bool(self.get_setting(self.SETTING.AUTO_RECONNECT))
        )
        switch.connect("state-set", self.signals.auto_reconnect_set)
        self.switches.append(switch)
        list_box.append(row)

        frame.set_child(list_box)
        self.pref_box.append(frame)

        # The native backend only ever removes profiles tagged
        # ``managed-by=eovpn-pro`` (see eovpn_connection_is_managed() in
        # subprojects/networkmanager/eovpn_nm.c), so the label must not imply a
        # system-wide wipe.
        # بک‌اند بومی فقط پروفایل‌های دارای برچسب `managed-by=eovpn-pro` را حذف
        # می‌کند (تابع eovpn_connection_is_managed در فایل eovpn_nm.c)، بنابراین
        # برچسب دکمه نباید پاک‌سازی سراسری سیستم را القا کند.
        self.remove_all_vpn_btn = Gtk.Button.new_with_label(
            gettext.gettext("Delete All eOVPN-Pro Profiles")
        )
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
        backend_frame = Gtk.Frame.new()
        backend_list_box = Gtk.ListBox.new()
        backend_frame.add_css_class("m-10")
        backend_list_box.add_css_class("rich-list")

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

        try:
            nm = NetworkManager(None)
            version = nm.version()
            if version:
                self.combobox.append("networkmanager", gettext.gettext("{} (OpenVPN 2)").format(version))
        except Exception as exc:
            logger.debug("NetworkManager module not available: %s", exc)

        try:
            ovpn3 = OpenVPN3(None)
            ovpn3_version = ovpn3.version()
            if ovpn3_version:
                self.combobox.append("openvpn3", gettext.gettext("OpenVPN 3 {}").format(ovpn3_version))
        except Exception as exc:
            logger.debug("OpenVPN 3 module not available: %s", exc)

        self.combobox.set_property("active-id", manager)

        h_box1.append(icon1)
        h_box1.append(v_box1)
        h_box1.append(self.combobox)
        row1.set_child(h_box1)
        backend_list_box.append(row1)

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

        h_box2.append(icon2)
        h_box2.append(v_box2)
        h_box2.append(self.dco_switch)
        self.dco_row.set_child(h_box2)
        backend_list_box.append(self.dco_row)

        backend_frame.set_child(backend_list_box)
        self.backend_box.append(backend_frame)

        self.dco_row.set_visible(manager == "openvpn3")
        self.dco_switch.connect("state-set", self.signals.openvpn3_dco_set)

    def _wire_signals(self):
        # Connect signals
        self.reset_btn.connect(
            "clicked",
            self.signals.on_reset_btn_clicked,
            [self.config_source_entry, self.username_entry, self.password_entry],
            [self.ca_chooser_btn],
            self.switches,
            self.window
        )
        self.config_source_entry.connect("changed", self.signals.process_config_entry, self.revealer)
        self.zip_file_chooser_dialog.connect(
            "response", self.signals.process_zip, self.config_source_entry, self.revealer
        )
        self.folder_file_chooser_dialog.connect(
            "response", self.signals.process_folder, self.config_source_entry, self.revealer
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
        self.ca_file_chooser_dialog.connect("response", self.signals.process_ca, self.ca_chooser_btn)
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
        dialog = Gtk.AlertDialog.new(
            gettext.gettext("Delete all eOVPN-Pro profiles?")
        )
        dialog.set_detail(
            gettext.gettext(
                "Every VPN profile that eOVPN-Pro created in NetworkManager will be "
                "permanently removed. VPN profiles added by other applications are "
                "not affected. This action cannot be undone."
            )
        )
        dialog.set_buttons([
            gettext.gettext("Cancel"),
            gettext.gettext("Delete Profiles"),
        ])
        dialog.set_cancel_button(0)
        # Cancel is also the default so that Enter or Escape never destroys data.
        # «انصراف» دکمهٔ پیش‌فرض هم هست تا فشردن Enter یا Escape هرگز داده‌ای را
        # از بین نبرد.
        dialog.set_default_button(0)
        dialog.choose(self.window, None, self._on_delete_all_confirmed, None)

    def _on_delete_all_confirmed(self, dialog: Gtk.AlertDialog, result, *args):
        """
        Deletes the managed profiles only when the destructive button was chosen.
        فقط در صورتی که دکمهٔ مخرب انتخاب شده باشد، پروفایل‌های مدیریت‌شده را حذف می‌کند.
        """
        try:
            if dialog.choose_finish(result) == 1:
                NetworkManager(None).delete_all_connections()
                logger.info("eOVPN-Pro managed VPN profiles were deleted by user confirmation.")
        except GLib.Error as error:
            # Dismissing the dialog (Escape) raises DIALOG_ERROR_DISMISSED; that
            # is a normal cancellation and must not be logged as a failure.
            # بستن دیالوگ با Escape خطای DIALOG_ERROR_DISMISSED می‌دهد که یک
            # انصراف عادی است و نباید به‌عنوان خطا ثبت شود.
            logger.debug("Delete-all dialog dismissed: %s", error.message)
        except Exception as e:
            logger.error("Delete-all confirmation failed: %s", e)

    def show(self):
        self.setup()
        self.window.show()


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

    def process_zip(self, chooser, response, entry, revealer):
        if response == Gtk.ResponseType.ACCEPT:
            path = chooser.get_file().get_path()
            eb = Gtk.EntryBuffer()
            eb.set_text(path, len(path))
            self.set_setting(self.SETTING.REMOTE, path)
            entry.set_buffer(eb)
            revealer.set_reveal_child(True)

    def process_folder(self, chooser, response, entry, revealer):
        if response == Gtk.ResponseType.ACCEPT:
            path = chooser.get_file().get_path()
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
            on_password_stored
        )
        return GLib.SOURCE_REMOVE

    def process_ca(self, chooser, response, button):
        if response == Gtk.ResponseType.ACCEPT:
            ca_path = chooser.get_file().get_path()
            self.set_setting(self.SETTING.CA, ca_path)
            button.set_label(chooser.get_file().get_basename())

    def notification_set(self, switch, state):
        self.set_setting(self.SETTING.NOTIFICATIONS, state)

    def show_flag_set(self, switch, state):
        self.set_setting(self.SETTING.SHOW_FLAG, state)
        flag_img = self.retrieve(StorageItem.FLAG)
        if flag_img:
            if state:
                flag_img.show()
            else:
                flag_img.hide()

    def dark_theme_set(self, switch, state):
        gtk_settings = Gtk.Settings().get_default()
        self.set_setting(self.SETTING.DARK_THEME, state)
        if gtk_settings:
            gtk_settings.set_property("gtk-application-prefer-dark-theme", state)

    def auto_reconnect_set(self, switch, state):
        self.set_setting(self.SETTING.AUTO_RECONNECT, state)

    def on_reset_btn_clicked(self, button, entries, buttons, switches, window):
        self.reset_all_settings()
        self.set_session_password(None)

        with contextlib.suppress(Exception):
            shutil.rmtree(self.EOVPN_OVPN_CONFIG_DIR)

        for e in entries:
            e.set_text('')
        for b in buttons:
            b.set_label('(None)')
        for s in switches:
            s.set_state(False)

        GLib.idle_add(self.remove_only, True)
        flag_img = self.retrieve(StorageItem.FLAG)
        if flag_img:
            flag_img.hide()

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
