"""
eOVPN-Pro settings, privacy, credentials, and backend preferences.
تنظیمات، حریم خصوصی، اطلاعات احراز هویت و بک‌اند eOVPN-Pro.

The window uses explicit save/import actions for operations with side effects,
shows actionable status feedback, and confirms every destructive operation.
این پنجره برای عملیات اثرگذار دکمه صریح ذخیره/واردکردن، بازخورد قابل‌اقدام و
تأیید جداگانه برای همه عملیات مخرب ارائه می‌دهد.
"""

from __future__ import annotations

import gettext
import logging
import shutil
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from .connection_manager import (
    BackendUnavailableError,
    NetworkManager,
    OpenVPN3,
)
from .context import ApplicationContext
from .dialogs.confirm import confirm_action
from .eovpn_base import Base, StorageItem
from .secret_store import DEFAULT_SECRET_STORE

logger = logging.getLogger(__name__)
_ = gettext.gettext


class SettingsWindow(Base, Gtk.Builder):
    """Professional modal preferences controller / کنترلر حرفه‌ای پنجره تنظیمات."""

    def __init__(self, context: ApplicationContext | None = None) -> None:
        Base.__init__(self, context)
        Gtk.Builder.__init__(self)
        self.signals = SettingsSignals(self, self.context)
        self._is_setup = False
        self._loading_credentials = False
        self.original_username = self.get_setting(self.SETTING.AUTH_USER)

        self.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/settings.ui")
        self.window: Gtk.Window = self.get_object("settings_window")
        self.window.set_title(_("{} Settings").format(self.APP_NAME))
        self.window.set_default_size(620, 600)
        parent = self.retrieve(StorageItem.MAIN_WINDOW)
        if isinstance(parent, Gtk.Window):
            self.window.set_transient_for(parent)
        self.window.set_modal(True)
        self.store(StorageItem.SETTINGS_WINDOW, self.window)
        self.store("settings_window_instance", self)

    @staticmethod
    def _section_title(title: str, subtitle: str | None = None) -> Gtk.Box:
        """Builds a consistent section heading / ساخت عنوان یکدست برای بخش تنظیمات."""
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        label = Gtk.Label.new(title)
        label.set_halign(Gtk.Align.START)
        label.add_css_class("title-4")
        box.append(label)
        if subtitle:
            description = Gtk.Label.new(subtitle)
            description.set_halign(Gtk.Align.START)
            description.set_xalign(0.0)
            description.set_wrap(True)
            description.add_css_class("dim-label")
            description.add_css_class("caption")
            box.append(description)
        return box

    @staticmethod
    def _icon_row(icon_name: str, child: Gtk.Widget) -> Gtk.Box:
        """Wraps a control with a symbolic icon / قراردادن کنترل کنار آیکون نمادین."""
        row = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 8)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(18)
        icon.add_css_class("dim-label")
        row.append(icon)
        child.set_hexpand(True)
        row.append(child)
        return row

    @staticmethod
    def _scroll_page(child: Gtk.Widget) -> Gtk.ScrolledWindow:
        """Wraps a preference page for small screens / قراردادن صفحه در اسکرول برای نمایشگر کوچک."""
        scroller = Gtk.ScrolledWindow.new()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(child)
        return scroller

    @staticmethod
    def _switch_row(
        title: str,
        subtitle: str,
        icon_name: str,
        state: bool,
    ) -> tuple[Gtk.ListBoxRow, Gtk.Switch]:
        """Builds an accessible preference switch / ساخت سوییچ دسترس‌پذیر تنظیمات."""
        row = Gtk.ListBoxRow.new()
        row.set_selectable(False)
        content = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 12)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(12)
        content.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(20)
        text = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        text.set_hexpand(True)
        title_label = Gtk.Label.new(title)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_xalign(0.0)
        title_label.add_css_class("bold")
        subtitle_label = Gtk.Label.new(subtitle)
        subtitle_label.set_halign(Gtk.Align.START)
        subtitle_label.set_xalign(0.0)
        subtitle_label.set_wrap(True)
        subtitle_label.add_css_class("dim-label")
        subtitle_label.add_css_class("caption")
        text.append(title_label)
        text.append(subtitle_label)

        switch = Gtk.Switch.new()
        switch.set_active(state)
        switch.set_valign(Gtk.Align.CENTER)
        content.append(icon)
        content.append(text)
        content.append(switch)
        row.set_child(content)
        return row, switch

    def _set_status(self, label: Gtk.Label, message: str, success: bool | None) -> None:
        """Updates an inline success/error status / به‌روزرسانی وضعیت موفق یا خطا."""
        label.set_text(message)
        label.set_visible(bool(message))
        label.remove_css_class("status-success")
        label.remove_css_class("status-error")
        if success is True:
            label.add_css_class("status-success")
        elif success is False:
            label.add_css_class("status-error")

    def setup(self) -> None:
        """Builds the settings UI once / ساخت یک‌باره رابط تنظیمات."""
        if self._is_setup:
            return
        self._is_setup = True

        header: Gtk.HeaderBar = self.get_object("settings_header_bar")
        self.reset_button = Gtk.Button.new_with_label(_("Reset"))
        self.reset_button.add_css_class("destructive-action")
        self.reset_button.set_tooltip_text(_("Reset settings and remove imported configurations"))
        header.pack_start(self.reset_button)
        self.spinner = Gtk.Spinner.new()
        header.pack_end(self.spinner)

        stack = Gtk.Stack.new()
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        switcher = Gtk.StackSwitcher.new()
        switcher.set_stack(stack)
        header.set_title_widget(switcher)
        self.window.set_child(stack)

        setup_page = self._build_setup_page()
        general_page = self._build_general_page()
        backend_page = self._build_backend_page()
        stack.add_titled(self._scroll_page(setup_page), "setup", _("Setup"))
        stack.add_titled(self._scroll_page(general_page), "general", _("General"))
        stack.add_titled(self._scroll_page(backend_page), "backend", _("Backend"))

        self.reset_button.connect("clicked", self._confirm_reset)

    def _build_setup_page(self) -> Gtk.Widget:
        page = Gtk.Box.new(Gtk.Orientation.VERTICAL, 14)
        page.set_margin_top(18)
        page.set_margin_bottom(18)
        page.set_margin_start(18)
        page.set_margin_end(18)

        page.append(
            self._section_title(
                _("Configuration Source"),
                _("Use a local folder/ZIP or a verified HTTPS URL. Plain HTTP is blocked."),
            )
        )
        source_controls = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        self.source_entry = Gtk.Entry.new()
        self.source_entry.set_placeholder_text("https://example.com/vpn/configs.zip")
        self.source_entry.set_hexpand(True)
        source = self.get_setting(self.SETTING.REMOTE)
        if source:
            self.source_entry.set_text(source)
        zip_button = Gtk.Button.new_from_icon_name("package-x-generic-symbolic")
        zip_button.set_tooltip_text(_("Choose ZIP File"))
        folder_button = Gtk.Button.new_from_icon_name("folder-open-symbolic")
        folder_button.set_tooltip_text(_("Choose Local Folder"))
        source_controls.append(self.source_entry)
        source_controls.append(zip_button)
        source_controls.append(folder_button)
        page.append(source_controls)

        self.validate_button = Gtk.Button.new_with_label(_("Validate & Import Securely"))
        self.validate_button.add_css_class("suggested-action")
        self.validate_button.set_sensitive(bool(self.source_entry.get_text().strip()))
        page.append(self.validate_button)
        self.import_status = Gtk.Label.new("")
        self.import_status.set_halign(Gtk.Align.START)
        self.import_status.set_wrap(True)
        self.import_status.set_visible(False)
        page.append(self.import_status)

        source_chooser = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
        source_chooser.set_transient_for(self.window)
        source_filter = Gtk.FileFilter()
        source_filter.set_name(_("ZIP archives"))
        source_filter.add_mime_type("application/zip")
        source_chooser.add_filter(source_filter)
        folder_chooser = Gtk.FileChooserNative(action=Gtk.FileChooserAction.SELECT_FOLDER)
        folder_chooser.set_transient_for(self.window)
        home = Gio.File.new_for_path(GLib.get_home_dir())
        source_chooser.set_current_folder(home)
        folder_chooser.set_current_folder(home)
        zip_button.connect("clicked", lambda *_: source_chooser.show())
        folder_button.connect("clicked", lambda *_: folder_chooser.show())

        separator = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(8)
        page.append(separator)
        page.append(
            self._section_title(
                _("Authentication"),
                _("Passwords are saved only after you explicitly press Save Credentials."),
            )
        )

        auth_header = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 8)
        auth_label = Gtk.Label.new(_("Use username and password"))
        auth_label.set_hexpand(True)
        auth_label.set_halign(Gtk.Align.START)
        self.auth_switch = Gtk.Switch.new()
        self.auth_switch.set_active(bool(self.get_setting(self.SETTING.REQ_AUTH)))
        auth_header.append(auth_label)
        auth_header.append(self.auth_switch)
        page.append(auth_header)

        self.auth_fields = Gtk.Box.new(Gtk.Orientation.VERTICAL, 8)
        self.auth_fields.set_sensitive(self.auth_switch.get_active())
        self.username_entry = Gtk.Entry.new()
        self.username_entry.set_placeholder_text(_("Username / Email"))
        if self.original_username:
            self.username_entry.set_text(self.original_username)
        self.password_entry = Gtk.PasswordEntry.new()
        self.password_entry.set_placeholder_text(_("Password"))
        self.password_entry.set_show_peek_icon(True)
        self.ca_button = Gtk.Button.new_with_label(_("Choose CA certificate (optional)"))
        ca_path = self.get_setting(self.SETTING.CA)
        if ca_path:
            self.ca_button.set_label(Path(ca_path).name)
        self.auth_fields.append(self._icon_row("avatar-default-symbolic", self.username_entry))
        self.auth_fields.append(self._icon_row("dialog-password-symbolic", self.password_entry))
        self.auth_fields.append(self._icon_row("application-certificate-symbolic", self.ca_button))

        self.save_credentials_button = Gtk.Button.new_with_label(_("Save Credentials Securely"))
        self.save_credentials_button.add_css_class("suggested-action")
        self.auth_fields.append(self.save_credentials_button)
        self.credential_status = Gtk.Label.new("")
        self.credential_status.set_halign(Gtk.Align.START)
        self.credential_status.set_wrap(True)
        self.credential_status.set_visible(False)
        self.auth_fields.append(self.credential_status)
        page.append(self.auth_fields)

        ca_chooser = Gtk.FileChooserNative(action=Gtk.FileChooserAction.OPEN)
        ca_chooser.set_transient_for(self.window)
        ca_filter = Gtk.FileFilter()
        ca_filter.set_name(_("Certificates"))
        ca_filter.add_pattern("*.crt")
        ca_filter.add_pattern("*.pem")
        ca_filter.add_pattern("*.ca")
        ca_chooser.add_filter(ca_filter)
        ca_chooser.set_current_folder(
            Gio.File.new_for_path(self.EOVPN_OVPN_CONFIG_DIR)
        )
        self.ca_button.connect("clicked", lambda *_: ca_chooser.show())

        self.source_entry.connect("changed", self.signals.process_source)
        source_chooser.connect("response", self.signals.process_file_chooser, self.source_entry)
        folder_chooser.connect("response", self.signals.process_file_chooser, self.source_entry)
        ca_chooser.connect("response", self.signals.process_ca)
        self.validate_button.connect("clicked", self.signals.import_configurations)
        self.auth_switch.connect("state-set", self.signals.set_auth_enabled)
        self.username_entry.connect("changed", self.signals.process_username)
        self.password_entry.connect("changed", self.signals.process_password)
        self.save_credentials_button.connect("clicked", self.signals.save_credentials)

        if self.original_username:
            def apply_password(success: bool, password: str | None) -> None:
                if not success:
                    return
                self._loading_credentials = True
                self.password_entry.set_text(password or "")
                self._loading_credentials = False

            DEFAULT_SECRET_STORE.lookup_async(self.original_username, apply_password)
        return page

    def _build_general_page(self) -> Gtk.Widget:
        page = Gtk.Box.new(Gtk.Orientation.VERTICAL, 14)
        page.set_margin_top(18)
        page.set_margin_bottom(18)
        page.set_margin_start(18)
        page.set_margin_end(18)
        page.append(
            self._section_title(
                _("Experience & Privacy"),
                _("Privacy-sensitive network lookups are opt-in and can be disabled at any time."),
            )
        )

        frame = Gtk.Frame.new()
        list_box = Gtk.ListBox.new()
        list_box.add_css_class("rich-list")
        frame.set_child(list_box)
        self.preference_switches: list[Gtk.Switch] = [self.auth_switch]

        preferences = (
            (
                _("Notifications"),
                _("Show connection and error notifications."),
                "preferences-system-notifications-symbolic",
                self.SETTING.NOTIFICATIONS,
                self.signals.set_notifications,
            ),
            (
                _("Country Indicator"),
                _("Show a Unicode country flag after an approved IP lookup."),
                "preferences-desktop-locale-symbolic",
                self.SETTING.SHOW_FLAG,
                self.signals.set_show_flag,
            ),
            (
                _("Public IP Lookup"),
                _("Contact documented HTTPS providers to display your public IP and country."),
                "network-workgroup-symbolic",
                self.SETTING.PUBLIC_IP_LOOKUP,
                self.signals.set_public_ip_lookup,
            ),
            (
                _("Dark Appearance"),
                _("Prefer the dark GTK color scheme."),
                "weather-clear-night-symbolic",
                self.SETTING.DARK_THEME,
                self.signals.set_dark_theme,
            ),
            (
                _("Auto Reconnect"),
                _("Retry after an unexpected drop; this is not a kill switch."),
                "network-wired-symbolic",
                self.SETTING.AUTO_RECONNECT,
                self.signals.set_auto_reconnect,
            ),
        )
        for title, subtitle, icon, key, handler in preferences:
            row, switch = self._switch_row(
                title, subtitle, icon, bool(self.get_setting(key))
            )
            switch.connect("state-set", handler)
            self.preference_switches.append(switch)
            list_box.append(row)
        page.append(frame)

        self.remove_profiles_button = Gtk.Button.new_with_label(
            _("Remove eOVPN NetworkManager Profiles…")
        )
        self.remove_profiles_button.add_css_class("destructive-action")
        self.remove_profiles_button.set_tooltip_text(
            _("Only profiles whose UUID was created and recorded by eOVPN are removed.")
        )
        self.remove_profiles_button.connect("clicked", self._confirm_remove_profiles)
        page.append(self.remove_profiles_button)
        return page

    def _build_backend_page(self) -> Gtk.Widget:
        page = Gtk.Box.new(Gtk.Orientation.VERTICAL, 14)
        page.set_margin_top(18)
        page.set_margin_bottom(18)
        page.set_margin_start(18)
        page.set_margin_end(18)
        page.append(
            self._section_title(
                _("Connection Backend"),
                _(
                    "NetworkManager is recommended. OpenVPN 3 appears only "
                    "when its system service is available."
                ),
            )
        )

        self.backend_combo = Gtk.ComboBoxText.new()
        try:
            version = NetworkManager(None, context=self.context).version()
            if version:
                self.backend_combo.append(
                    "networkmanager", _("NetworkManager {} (OpenVPN 2)").format(version)
                )
        except Exception as exc:
            logger.error("NetworkManager backend discovery failed: %s", exc)

        try:
            version = OpenVPN3(None, context=self.context).version()
            if version:
                self.backend_combo.append("openvpn3", _("OpenVPN 3 {}").format(version))
        except BackendUnavailableError:
            logger.debug("Optional OpenVPN 3 backend is unavailable.")

        manager_name = self.get_setting(self.SETTING.MANAGER) or "networkmanager"
        self.backend_combo.set_active_id(manager_name)
        page.append(self._icon_row("network-wired-symbolic", self.backend_combo))

        self.dco_row, self.dco_switch = self._switch_row(
            _("Data Channel Offload (DCO)"),
            _("Use kernel data-channel acceleration when OpenVPN 3 and the host support it."),
            "speedometer-symbolic",
            bool(self.get_setting(self.SETTING.OPENVPN3_DCO)),
        )
        self.dco_row.set_visible(manager_name == "openvpn3")
        page.append(self.dco_row)
        self.backend_status = Gtk.Label.new("")
        self.backend_status.set_halign(Gtk.Align.START)
        self.backend_status.set_wrap(True)
        self.backend_status.set_visible(False)
        page.append(self.backend_status)

        self.backend_combo.connect("changed", self.signals.select_backend)
        self.dco_switch.connect("state-set", self.signals.set_openvpn3_dco)
        return page

    def _confirm_remove_profiles(self, _button: Gtk.Button) -> None:
        confirm_action(
            self.window,
            title=_("Remove eOVPN profiles?"),
            detail=_(
                "Only NetworkManager profile UUIDs recorded by eOVPN will be removed. "
                "Profiles created by other applications are never touched."
            ),
            confirm_label=_("Remove Profiles"),
            cancel_label=_("Cancel"),
            callback=self._remove_managed_profiles,
        )

    def _remove_managed_profiles(self, confirmed: bool) -> None:
        if not confirmed:
            return
        try:
            deleted, failed = NetworkManager(
                None, context=self.context
            ).delete_managed_connections()
            message = _("Removed {} managed profile(s); {} could not be removed.").format(
                deleted, failed
            )
            self._set_status(self.backend_status, message, failed == 0)
        except Exception as exc:
            self._set_status(self.backend_status, str(exc), False)

    def _confirm_reset(self, _button: Gtk.Button) -> None:
        confirm_action(
            self.window,
            title=_("Reset eOVPN settings?"),
            detail=_(
                "Imported configurations and local preferences will be removed. "
                "Other applications and their VPN profiles are not affected."
            ),
            confirm_label=_("Reset eOVPN"),
            cancel_label=_("Cancel"),
            callback=self.signals.perform_reset,
        )

    def show(self) -> None:
        self.setup()
        self.window.present()


class SettingsSignals(Base):
    """Side-effect handlers for one SettingsWindow / مدیریت رویدادهای یک پنجره تنظیمات."""

    def __init__(
        self,
        view: SettingsWindow,
        context: ApplicationContext,
    ) -> None:
        super().__init__(context)
        self.view = view
        self._changing_backend = False

    def process_source(self, entry: Gtk.Entry) -> None:
        text = entry.get_text().strip()
        self.set_setting(self.SETTING.REMOTE, text or None)
        self.view.validate_button.set_sensitive(bool(text))
        self.view._set_status(self.view.import_status, "", None)

    def process_file_chooser(self, chooser, response, entry: Gtk.Entry) -> None:
        if response != Gtk.ResponseType.ACCEPT:
            return
        selected = chooser.get_file()
        path = selected.get_path() if selected else None
        if path:
            entry.set_text(path)

    def import_configurations(self, _button: Gtk.Button) -> None:
        self.view.validate_button.set_sensitive(False)
        self.view._set_status(
            self.view.import_status,
            _("Validating and importing into a private repository…"),
            None,
        )

        def completed(success: bool, message: str, _result) -> None:
            self.view.validate_button.set_sensitive(True)
            self.view._set_status(self.view.import_status, message, success)

        self.validate_and_load(self.view.spinner, self.view.ca_button, completed)

    def set_auth_enabled(self, _switch: Gtk.Switch, state: bool) -> None:
        self.set_setting(self.SETTING.REQ_AUTH, state)
        self.view.auth_fields.set_sensitive(state)

    def process_username(self, entry: Gtk.Entry) -> None:
        username = entry.get_text().strip()
        self.set_setting(self.SETTING.AUTH_USER, username or None)
        password = self.view.password_entry.get_text()
        DEFAULT_SECRET_STORE.set_session(username or None, password or None)

    def process_password(self, entry: Gtk.PasswordEntry) -> None:
        username = self.view.username_entry.get_text().strip()
        DEFAULT_SECRET_STORE.set_session(username or None, entry.get_text() or None)
        if self.view._loading_credentials:
            return
        self.view._set_status(
            self.view.credential_status,
            _("Unsaved credential changes"),
            None,
        )

    def save_credentials(self, _button: Gtk.Button) -> None:
        username = self.view.username_entry.get_text().strip()
        password = self.view.password_entry.get_text()
        if not username:
            self.view._set_status(
                self.view.credential_status,
                _("Enter a username before saving credentials."),
                False,
            )
            return
        self.view.save_credentials_button.set_sensitive(False)
        old_username = self.view.original_username
        clearing = not bool(password)

        def saved(success: bool, error: str | None) -> None:
            def update_ui() -> bool:
                self.view.save_credentials_button.set_sensitive(True)
                if success:
                    message = (
                        _("Saved password removed from Secret Service.")
                        if clearing
                        else _("Credentials saved in Secret Service.")
                    )
                else:
                    message = _(
                        "Secret Service was unavailable; the password is retained only for this session."
                    )
                    if error:
                        logger.debug("Credential persistence failed: %s", error)
                self.view._set_status(self.view.credential_status, message, success)
                self.view.original_username = username
                return False

            GLib.idle_add(update_ui)
            if old_username and old_username != username:
                DEFAULT_SECRET_STORE.clear_async(old_username)

        DEFAULT_SECRET_STORE.store_async(username, password, saved)

    def process_ca(self, chooser, response) -> None:
        if response != Gtk.ResponseType.ACCEPT:
            return
        selected = chooser.get_file()
        path = selected.get_path() if selected else None
        if path:
            self.set_setting(self.SETTING.CA, path)
            self.view.ca_button.set_label(Path(path).name)

    def set_notifications(self, _switch, state: bool) -> None:
        self.set_setting(self.SETTING.NOTIFICATIONS, state)

    def set_show_flag(self, _switch, state: bool) -> None:
        self.set_setting(self.SETTING.SHOW_FLAG, state)
        flag = self.retrieve(StorageItem.FLAG)
        if flag is not None:
            flag.set_visible(state)

    def set_public_ip_lookup(self, _switch, state: bool) -> None:
        self.set_setting(self.SETTING.PUBLIC_IP_LOOKUP, state)
        main_window = self.retrieve("main_window_instance")
        if main_window is not None:
            main_window.update_ip_flag_async()

    def set_dark_theme(self, _switch, state: bool) -> None:
        self.set_setting(self.SETTING.DARK_THEME, state)
        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.set_property("gtk-application-prefer-dark-theme", state)

    def set_auto_reconnect(self, _switch, state: bool) -> None:
        self.set_setting(self.SETTING.AUTO_RECONNECT, state)
        if not state:
            main_window = self.retrieve("main_window_instance")
            if main_window is not None:
                main_window.cancel_reconnect()

    def set_openvpn3_dco(self, _switch, state: bool) -> None:
        self.set_setting(self.SETTING.OPENVPN3_DCO, state)

    def select_backend(self, combo: Gtk.ComboBoxText) -> None:
        if self._changing_backend:
            return
        backend_id = combo.get_active_id()
        if not backend_id:
            return
        current_record = self.retrieve("CM") or {}
        current = current_record.get("instance") if isinstance(current_record, dict) else None
        current_name = current_record.get("name") if isinstance(current_record, dict) else None
        if current_name == backend_id:
            self.view.dco_row.set_visible(backend_id == "openvpn3")
            return
        try:
            if current is not None and current.status():
                raise RuntimeError(_("Disconnect the current VPN before changing backends."))
            if current is not None:
                current.stop_watch()
            callback = self.retrieve("on_connection_event")
            manager = (
                NetworkManager(callback, context=self.context)
                if backend_id == "networkmanager"
                else OpenVPN3(callback, context=self.context)
            )
            self.store("CM", {"name": backend_id, "instance": manager})
            self.set_setting(self.SETTING.MANAGER, backend_id)
            self.view.dco_row.set_visible(backend_id == "openvpn3")
            self.view._set_status(
                self.view.backend_status,
                _("Backend changed successfully."),
                True,
            )
        except Exception as exc:
            self._changing_backend = True
            combo.set_active_id(current_name or "networkmanager")
            self._changing_backend = False
            self.view._set_status(self.view.backend_status, str(exc), False)

    def perform_reset(self, confirmed: bool) -> None:
        if not confirmed:
            return
        username = self.get_setting(self.SETTING.AUTH_USER)
        if username:
            DEFAULT_SECRET_STORE.clear_async(username)
        DEFAULT_SECRET_STORE.clear_session()
        try:
            # Remove recorded eOVPN profiles before resetting their UUID list.
            # پروفایل‌های ثبت‌شده پیش از پاک‌شدن فهرست UUID حذف می‌شوند.
            NetworkManager(
                None, context=self.context
            ).delete_managed_connections()
        except Exception as exc:
            logger.warning("Could not remove every managed profile during reset: %s", exc)
        self.reset_all_settings()
        shutil.rmtree(self.EOVPN_OVPN_CONFIG_DIR, ignore_errors=True)
        self.config_repository.ensure()
        self.remove_only()
        self.view.source_entry.set_text("")
        self.view.username_entry.set_text("")
        self.view.password_entry.set_text("")
        self.view.ca_button.set_label(_("Choose CA certificate (optional)"))
        self.view.auth_switch.set_active(False)
        self.view._set_status(
            self.view.import_status,
            _("eOVPN settings and imported configurations were reset."),
            True,
        )
