"""
eOVPN-Pro shared UI foundation, settings access, and configuration list model.
زیرساخت مشترک رابط کاربری، تنظیمات و مدل فهرست کانفیگ‌های eOVPN-Pro.

The module intentionally keeps only lightweight application-wide facilities.
Security-sensitive imports and credentials are delegated to dedicated services.
این ماژول فقط امکانات سراسری سبک را نگه می‌دارد و واردکردن امن کانفیگ و مدیریت
رمزها را به سرویس‌های اختصاصی واگذار می‌کند.
"""

from __future__ import annotations

import gettext
import json
import logging
import os
import shutil
import threading
from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Notify", "0.7")
from gi.repository import Gio, GLib, GObject, Gtk, Notify, Pango

from .auto_connect import format_proto_badge, parse_ovpn_protocols, proto_badge_css
from .config_import import ImportResult
from .config_repository import ConfigRepository
from .constants import (
    APP_ID,
    APP_NAME,
    CONFIG_DIR_NAME,
    CONFIGS_DIR_NAME,
    LEGACY_APP_IDS,
    RESOURCE_PREFIX,
)
from .context import ApplicationContext
from .secret_store import DEFAULT_SECRET_STORE

logger = logging.getLogger(__name__)


class ConfigItem(GObject.Object):
    """List model item for one OpenVPN file / آیتم مدل برای یک فایل OpenVPN."""

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.name = name

    def __repr__(self) -> str:
        return self.name


class ConfigRow(Gtk.ListBoxRow):
    """
    Accessible server row with favorite, protocol, latency, and edit controls.
    ردیف دسترس‌پذیر سرور با کنترل علاقه‌مندی، پروتکل، تأخیر و ویرایش.
    """

    def __init__(
        self,
        filename: str,
        ovpn_dir: str,
        favorites: set[str] | None = None,
        on_favorite_toggled: Callable[[str, bool], None] | None = None,
        protocols: set[str] | frozenset[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.filename = filename
        self.ovpn_dir = ovpn_dir
        self.on_favorite_toggled = on_favorite_toggled
        self.protocols = frozenset(protocols or ())
        is_favorite = filename in (favorites or set())

        container = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 8)
        container.set_margin_start(10)
        container.set_margin_end(8)
        container.set_margin_top(4)
        container.set_margin_bottom(4)

        self.fav_button = Gtk.ToggleButton()
        self.fav_button.set_icon_name(
            "starred-symbolic" if is_favorite else "non-starred-symbolic"
        )
        self.fav_button.set_active(is_favorite)
        self.fav_button.set_valign(Gtk.Align.CENTER)
        self.fav_button.add_css_class("flat")
        self.fav_button.add_css_class("server-fav-btn")
        self.fav_button.set_tooltip_text(
            gettext.gettext("Remove from Favorites")
            if is_favorite
            else gettext.gettext("Add to Favorites")
        )
        self.fav_button.connect("toggled", self._on_favorite_toggled)

        self.label = Gtk.Label.new(filename)
        self.label.set_halign(Gtk.Align.START)
        self.label.set_hexpand(True)
        self.label.set_xalign(0.0)
        self.label.set_ellipsize(Pango.EllipsizeMode.END)
        self.label.set_tooltip_text(filename)

        badge_text = format_proto_badge(self.protocols)
        self.proto_badge = Gtk.Label.new(badge_text)
        self.proto_badge.add_css_class("proto-badge")
        badge_css = proto_badge_css(self.protocols)
        if badge_css:
            self.proto_badge.add_css_class(badge_css)
        self.proto_badge.set_visible(bool(badge_text))
        self.proto_badge.set_valign(Gtk.Align.CENTER)
        if badge_text:
            self.proto_badge.set_tooltip_text(
                gettext.gettext("OpenVPN protocol: {}").format(badge_text)
            )

        self.latency_label = Gtk.Label.new("")
        self.latency_label.set_halign(Gtk.Align.END)
        self.latency_label.set_margin_end(8)

        self.edit_button = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        self.edit_button.set_has_frame(False)
        self.edit_button.set_tooltip_text(gettext.gettext("Edit Configuration"))
        self.edit_button.set_halign(Gtk.Align.END)
        self.edit_button.set_visible(False)
        self.edit_button.add_css_class("btn-no-dec")
        self.edit_button.connect("clicked", self._open_configuration)

        container.append(self.fav_button)
        container.append(self.label)
        container.append(self.proto_badge)
        container.append(self.latency_label)
        container.append(self.edit_button)
        self.set_child(container)

    def _open_configuration(self, _button: Gtk.Button) -> None:
        """Uses the desktop portal/default editor / استفاده از پورتال یا ویرایشگر پیش‌فرض."""
        target = Path(self.ovpn_dir, self.filename).resolve()
        try:
            Gio.AppInfo.launch_default_for_uri(target.as_uri(), None)
        except Exception as exc:
            logger.error("Could not open configuration editor for %s: %s", target, exc)

    def _on_favorite_toggled(self, button: Gtk.ToggleButton) -> None:
        """Updates and persists favorite state / به‌روزرسانی و ذخیره علاقه‌مندی."""
        active = button.get_active()
        button.set_icon_name("starred-symbolic" if active else "non-starred-symbolic")
        button.set_tooltip_text(
            gettext.gettext("Remove from Favorites")
            if active
            else gettext.gettext("Add to Favorites")
        )
        if self.on_favorite_toggled:
            self.on_favorite_toggled(self.filename, active)

    def set_edit_visible(self, visible: bool) -> None:
        """Shows or hides the edit action / نمایش یا پنهان‌سازی عملیات ویرایش."""
        self.edit_button.set_visible(visible)


class StorageItem:
    """Legacy registry keys / کلیدهای رجیستری سازگاری."""

    MAIN_WINDOW = "main-window"
    SETTINGS_WINDOW = "settings-window"
    LISTBOX = "listbox"
    LISTBOX_ROWS = "listbox-rows"
    LISTSTORE = "liststore"
    CONFIGS_LIST = "listbox-rows-index"
    FLAG = "flag"


class Settings:
    """Canonical GSettings keys / کلیدهای رسمی GSettings."""

    LAST_CONNECTED = "last-connected"
    LAST_CONNECTED_CURSOR = "last-connected-cursor"
    NOTIFICATIONS = "notifications"
    MANAGER = "manager"
    REQ_AUTH = "req-auth"
    CA = "ca"
    REMOTE = "remote"
    AUTH_USER = "auth-user"
    NM_ACTIVE_UUID = "nm-active-uuid"
    NM_OWNED_UUIDS = "nm-owned-uuids"
    OVPN3_SESSION_PATH = "openvpn3-session-path"
    OVPN3_CONFIG_PATH = "openvpn3-config-path"
    SHOW_FLAG = "show-flag"
    PUBLIC_IP_LOOKUP = "public-ip-lookup"
    LISTBOX_V_ADJUST = "listbox-v-adjust"
    LAYOUT = "layout"
    DARK_THEME = "dark-theme"
    OPENVPN3_DCO = "openvpn3-dco"
    AUTO_RECONNECT = "auto-reconnect"
    LANGUAGE = "language"
    FAVORITES = "favorite-configs"
    MIGRATION_COMPLETE = "migration-complete"

    # User-resettable keys; migration state is deliberately excluded.
    # کلیدهای قابل بازنشانی کاربر؛ وضعیت مهاجرت عمداً در فهرست نیست.
    all_settings = [
        LAST_CONNECTED,
        LAST_CONNECTED_CURSOR,
        NOTIFICATIONS,
        MANAGER,
        REQ_AUTH,
        CA,
        REMOTE,
        AUTH_USER,
        NM_ACTIVE_UUID,
        NM_OWNED_UUIDS,
        OVPN3_SESSION_PATH,
        OVPN3_CONFIG_PATH,
        SHOW_FLAG,
        PUBLIC_IP_LOOKUP,
        LISTBOX_V_ADJUST,
        LAYOUT,
        DARK_THEME,
        AUTO_RECONNECT,
        FAVORITES,
        LANGUAGE,
        OPENVPN3_DCO,
    ]

    # Keys that existed in the immediately previous application ID.
    # کلیدهایی که در شناسه قبلی برنامه وجود داشتند.
    legacy_settings = [
        LAST_CONNECTED,
        LAST_CONNECTED_CURSOR,
        NOTIFICATIONS,
        MANAGER,
        REQ_AUTH,
        CA,
        REMOTE,
        AUTH_USER,
        NM_ACTIVE_UUID,
        SHOW_FLAG,
        LISTBOX_V_ADJUST,
        LAYOUT,
        DARK_THEME,
        OPENVPN3_DCO,
        AUTO_RECONNECT,
        FAVORITES,
        LANGUAGE,
    ]


ImportCompletion = Callable[[bool, str, ImportResult | None], None]


class Base:
    """
    Shared metadata, settings, notifications, and configuration list helpers.
    امکانات مشترک متادیتا، تنظیمات، اعلان‌ها و فهرست کانفیگ‌ها.
    """

    def __init__(self, context: ApplicationContext | None = None) -> None:
        self.context = context or ApplicationContext()
        metadata_path = Path(__file__).with_name("metadata.json")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            metadata = {
                "APP_NAME": APP_NAME,
                "APP_ID": APP_ID,
                "APP_VERSION": "1.5.0",
                "COMMIT": "development",
                "AUTHOR": "Mahdi Bagheban",
                "AUTHOR_MAIL": "info@MahdiArts.ir",
                "AUTHOR_MAIL_SECONDARY": "mehdi.bagheban@gmail.com",
                "AUTHOR_WEBSITE": "https://www.MahdiArts.ir",
                "AUTHOR_DONATE": "https://www.MahdiArts.ir/donate",
            }

        self.APP_NAME = metadata.get("APP_NAME", APP_NAME)
        self.APP_ID = metadata.get("APP_ID", APP_ID)
        self.APP_VERSION = metadata.get("APP_VERSION", "1.5.0")
        self.APP_COMMIT = metadata.get("COMMIT", "development")
        self.AUTHOR = metadata.get("AUTHOR", "Mahdi Bagheban")
        self.AUTHOR_MAIL = metadata.get("AUTHOR_MAIL", "info@MahdiArts.ir")
        self.AUTHOR_MAIL_SECONDARY = metadata.get(
            "AUTHOR_MAIL_SECONDARY", "mehdi.bagheban@gmail.com"
        )
        self.AUTHOR_WEBSITE = metadata.get("AUTHOR_WEBSITE", "https://www.MahdiArts.ir")
        self.AUTHOR_DONATE = metadata.get(
            "AUTHOR_DONATE", "https://www.MahdiArts.ir/donate"
        )

        self.TRANSLATORS: dict[str, str] = {}
        self.EOVPN_SECRET_SCHEMA = DEFAULT_SECRET_STORE.schema
        self.EOVPN_CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), CONFIG_DIR_NAME)
        self.EOVPN_OVPN_CONFIG_DIR = os.path.join(
            self.EOVPN_CONFIG_DIR, CONFIGS_DIR_NAME
        )
        self.EOVPN_GRESOURCE_PREFIX = RESOURCE_PREFIX
        self.EOVPN_CSS = RESOURCE_PREFIX + "/css/main.css"
        self.SETTING = Settings()
        self.__settings = Gio.Settings.new(APP_ID)
        self._migrate_legacy_settings()
        self.config_repository = ConfigRepository(self.EOVPN_OVPN_CONFIG_DIR)
        self.config_repository.ensure()

    def _migrate_legacy_settings(self) -> None:
        """
        Copies user-set values once from earlier application IDs.
        کپی یک‌باره مقادیر کاربر از شناسه‌های پیشین برنامه.
        """
        if self.__settings.get_boolean(self.SETTING.MIGRATION_COMPLETE):
            return

        for legacy_id in LEGACY_APP_IDS:
            try:
                legacy = Gio.Settings.new(legacy_id)
            except Exception as exc:
                logger.debug("Legacy GSettings schema %s is unavailable: %s", legacy_id, exc)
                continue
            for key in self.SETTING.legacy_settings:
                try:
                    if self.__settings.get_user_value(key) is not None:
                        continue
                    old_value = legacy.get_user_value(key)
                    if old_value is not None:
                        self.__settings.set_value(key, old_value)
                except Exception as exc:
                    logger.debug("Could not migrate GSettings key %s: %s", key, exc)

        self.__settings.set_boolean(self.SETTING.MIGRATION_COMPLETE, True)
        Gio.Settings.sync()

    def set_session_password(self, password: str | None) -> None:
        """Compatibility helper for volatile credentials / تابع سازگاری رمز موقت."""
        DEFAULT_SECRET_STORE.set_session(
            self.get_setting(self.SETTING.AUTH_USER), password
        )

    def get_session_password(self) -> str | None:
        """Returns the current user's volatile password / بازگرداندن رمز موقت کاربر فعلی."""
        return DEFAULT_SECRET_STORE.get_session(
            self.get_setting(self.SETTING.AUTH_USER)
        )

    def store(self, item: str, obj: object) -> None:
        """Stores a per-application runtime reference / ذخیره ارجاع مخصوص همین برنامه."""
        self.context.set(item, obj)

    def retrieve(self, item: str) -> object | None:
        """Retrieves a per-application runtime reference / بازیابی ارجاع مخصوص همین برنامه."""
        return self.context.get(item)

    def _show_notification(self, summary: str, body: str) -> None:
        """Shows one desktop notification / نمایش یک اعلان دسکتاپ."""
        if self.get_setting(self.SETTING.NOTIFICATIONS) is False:
            return
        try:
            Notify.init(self.APP_ID)
            Notify.Notification.new(summary, body, self.APP_ID).show()
        except Exception as exc:
            logger.debug("Desktop notification failed: %s", exc)

    def send_connected_notification(self) -> None:
        self._show_notification(
            gettext.gettext("Connected"),
            gettext.gettext("Secure VPN connection established."),
        )

    def send_disconnected_notification(self) -> None:
        self._show_notification(
            gettext.gettext("Disconnected"),
            gettext.gettext("VPN tunnel disconnected."),
        )

    def send_error_notification(self, error_message: str) -> None:
        self._show_notification(gettext.gettext("Connection Error"), error_message)

    @staticmethod
    def get_country_flag_emoji(country_code: str | None) -> str:
        """
        Converts ISO-3166 alpha-2 to a Unicode flag without bundled artwork.
        تبدیل کد دوحرفی کشور به پرچم یونیکد بدون فایل گرافیکی جانبی.
        """
        code = (country_code or "").upper()
        if len(code) != 2 or not code.isascii() or not code.isalpha():
            return "🌐"
        return "".join(chr(0x1F1E6 + ord(char) - ord("A")) for char in code)

    def get_setting(self, key: str):
        """Returns a typed GSettings value / بازگرداندن مقدار نوع‌دار GSettings."""
        try:
            value = self.__settings.get_value(key).unpack()
        except Exception as exc:
            logger.debug("GSettings key %s is unavailable: %s", key, exc)
            return None
        if isinstance(value, str) and value == "null":
            return None
        return list(value) if isinstance(value, tuple) else value

    def set_setting(self, key: str, value) -> None:
        """Writes a supported Python value to GSettings / نوشتن مقدار پایتون در GSettings."""
        if value is None:
            self.__settings.reset(key)
            return

        variants = {
            bool: GLib.Variant.new_boolean,
            int: GLib.Variant.new_int32,
            float: GLib.Variant.new_double,
            str: GLib.Variant.new_string,
        }
        try:
            if isinstance(value, (list, tuple, set)):
                variant = GLib.Variant.new_strv([str(item) for item in value])
            else:
                factory = variants.get(type(value))
                if factory is None:
                    raise TypeError(f"Unsupported GSettings type: {type(value)!r}")
                variant = factory(value)
            self.__settings.set_value(key, variant)
        except Exception as exc:
            logger.error("Could not write GSettings key %s: %s", key, exc)

    def reset_all_settings(self) -> None:
        """Resets user settings while retaining an undo snapshot / بازنشانی همراه نسخه بازگشت."""
        backup: dict[str, GLib.Variant] = {}
        self.store("settings-backup", backup)
        for key in self.SETTING.all_settings:
            try:
                backup[key] = self.__settings.get_value(key)
                self.__settings.reset(key)
            except Exception as exc:
                logger.debug("Could not reset GSettings key %s: %s", key, exc)
        Gio.Settings.sync()

    def undo_reset_settings(self) -> None:
        """Restores the last reset snapshot / بازیابی آخرین نسخه پیش از بازنشانی."""
        backup = self.retrieve("settings-backup")
        if not isinstance(backup, dict):
            return
        for key, value in backup.items():
            try:
                self.__settings.set_value(key, value)
            except Exception as exc:
                logger.debug("Could not restore GSettings key %s: %s", key, exc)
        Gio.Settings.sync()

    def reset_paths(self) -> None:
        """Recreates the managed repository privately / بازسازی خصوصی مخزن مدیریت‌شده."""
        shutil.rmtree(self.EOVPN_OVPN_CONFIG_DIR, ignore_errors=True)
        self.config_repository.ensure()

    def get_favorites(self) -> set[str]:
        """Returns favorite filenames / بازگرداندن نام کانفیگ‌های محبوب."""
        return set(self.get_setting(self.SETTING.FAVORITES) or [])

    def toggle_favorite(self, filename: str, favorite: bool) -> None:
        """Persists one favorite state / ذخیره وضعیت علاقه‌مندی یک کانفیگ."""
        favorites = self.get_favorites()
        if favorite:
            favorites.add(filename)
        else:
            favorites.discard(filename)
        self.set_setting(self.SETTING.FAVORITES, sorted(favorites))

    def _notify_list_changed(self) -> None:
        hook = self.retrieve("on_list_changed")
        if callable(hook):
            try:
                hook()
            except Exception as exc:
                logger.debug("List-change hook failed: %s", exc)

    def load_only(self) -> int:
        """Loads private .ovpn files into the GTK model / بارگذاری فایل‌ها در مدل GTK."""
        self.store("latency_labels", {})
        self.store("proto_cache", {})
        self.store(StorageItem.LISTBOX_ROWS, [])
        favorites = self.get_favorites()

        def widget_factory(item: ConfigItem) -> ConfigRow:
            filename = str(item)
            proto_cache = self.retrieve("proto_cache")
            if not isinstance(proto_cache, dict):
                proto_cache = {}
                self.store("proto_cache", proto_cache)
            if filename not in proto_cache:
                proto_cache[filename] = parse_ovpn_protocols(
                    str(Path(self.EOVPN_OVPN_CONFIG_DIR, filename))
                )
            row = ConfigRow(
                filename,
                self.EOVPN_OVPN_CONFIG_DIR,
                favorites=favorites,
                on_favorite_toggled=self.retrieve("favorite_toggled_cb"),
                protocols=proto_cache[filename],
            )
            latency_labels = self.retrieve("latency_labels")
            if isinstance(latency_labels, dict):
                latency_labels[filename] = row.latency_label
            rows = self.retrieve(StorageItem.LISTBOX_ROWS)
            if isinstance(rows, list):
                rows.append(row)
            return row

        box = self.retrieve(StorageItem.LISTBOX)
        if box is None:
            return 0

        configs: list[str] = []
        try:
            for entry in Path(self.EOVPN_OVPN_CONFIG_DIR).iterdir():
                if entry.is_symlink() or not entry.is_file() or entry.suffix.lower() != ".ovpn":
                    continue
                try:
                    entry.chmod(0o600)
                except OSError as exc:
                    logger.warning("Could not harden permissions for %s: %s", entry, exc)
                    continue
                configs.append(entry.name)
            configs.sort(key=str.casefold)
        except OSError as exc:
            logger.error("Could not enumerate configuration repository: %s", exc)

        liststore = Gio.ListStore.new(ConfigItem)
        self.store(StorageItem.LISTSTORE, liststore)
        self.store(StorageItem.CONFIGS_LIST, configs)

        filter_model = self.retrieve("filter_model")
        if filter_model is not None:
            try:
                filter_model.set_model(liststore)
            except Exception as exc:
                logger.debug("Could not attach filter model: %s", exc)
                filter_model = None
        bind_model = filter_model if filter_model is not None else liststore
        box.bind_model(bind_model, widget_factory)
        for filename in configs:
            liststore.append(ConfigItem(filename))
        self._notify_list_changed()
        return len(configs)

    def remove_only(self, remove_path: bool = False) -> None:
        """Clears the model and optionally the managed files / پاک‌سازی مدل و در صورت نیاز فایل‌ها."""
        if remove_path:
            self.reset_paths()
        liststore = self.retrieve(StorageItem.LISTSTORE)
        if liststore is not None and hasattr(liststore, "remove_all"):
            liststore.remove_all()
        self.store(StorageItem.LISTBOX_ROWS, [])
        self.store(StorageItem.CONFIGS_LIST, [])
        self._notify_list_changed()

    def validate_and_load(
        self,
        spinner=None,
        ca_button=None,
        completion: ImportCompletion | None = None,
    ) -> None:
        """
        Runs a validated repository transaction off the GTK thread.
        اجرای تراکنش اعتبارسنجی‌شده مخزن خارج از نخ GTK.
        """
        source = self.get_setting(self.SETTING.REMOTE)
        if not source:
            message = gettext.gettext("Configuration source is empty.")
            if completion:
                completion(False, message, None)
            return

        if spinner is not None:
            spinner.start()

        def worker() -> None:
            result: ImportResult | None = None
            error: str | None = None
            try:
                result = self.config_repository.update(str(source))
            except Exception as exc:
                error = str(exc) or gettext.gettext("Configuration import failed.")
                logger.error("Configuration import failed: %s", exc)

            def apply_result() -> bool:
                if spinner is not None:
                    spinner.stop()
                if result is not None:
                    self.remove_only()
                    self.load_only()
                    if len(result.certificates) == 1:
                        certificate = result.certificates[0]
                        ca_path = str(Path(self.EOVPN_OVPN_CONFIG_DIR, certificate))
                        self.set_setting(self.SETTING.CA, ca_path)
                        if ca_button is not None:
                            ca_button.set_label(certificate)
                    message = gettext.gettext("{} configuration(s) imported securely.").format(
                        result.count
                    )
                    if completion:
                        completion(True, message, result)
                elif completion:
                    completion(
                        False,
                        error or gettext.gettext("Configuration import failed."),
                        None,
                    )
                return False

            GLib.idle_add(apply_result)

        threading.Thread(
            target=worker,
            name="eovpn-config-import",
            daemon=True,
        ).start()
