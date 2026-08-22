"""
eOVPN-Pro Base Application & State Management Module
ماژول هسته و مدیریت وضعیت برنامه در eOVPN-Pro

Provides global application definitions, settings management, notification dispatchers,
custom UI list widgets, and secure in-memory session stores.
شامل تعاریف کلی، مدیریت تنظیمات، سیستم اعلان‌ها، ویجت‌های اختصاصی لیست و حافظه موقت امن برای نشست‌ها.
"""

import os
import shutil
import logging
import threading
import json
import subprocess
import gettext
from pathlib import Path

import gi
gi.require_version('Notify', '0.7')
gi.require_version('Secret', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import GObject, Gtk, Gio, GLib, GdkPixbuf, Notify, Secret

from .utils import download_remote_to_destination
from .auto_connect import format_proto_badge, parse_ovpn_protocols, proto_badge_css

_builder_record: dict[str, Gtk.Builder] = {}
_storage_record: dict[str, object] = {}
_settings_backup: dict[str, GLib.Variant] = {}
_session_secrets: dict[str, str] = {}  # Secure in-RAM password store / ذخیره امن رمز در حافظه

EOVPN_SECRET_SCHEMA = Secret.Schema.new(
    "com.github.mahdi-arts.eovpn-pro",
    Secret.SchemaFlags.NONE,
    {"username": Secret.SchemaAttributeType.STRING}
)

logger = logging.getLogger(__name__)


class ConfigItem(GObject.Object):
    """
    Model item representing a single OpenVPN configuration entry.
    آیتم مدل مربوط به یک کانفیگ OpenVPN در ListStore.
    """
    def __init__(self, name: str, **kwargs):
        super(ConfigItem, self).__init__(**kwargs)
        self.name = name

    def __repr__(self) -> str:
        return str(self.name)


class ConfigRow(Gtk.ListBoxRow):
    """
    Custom ListBoxRow widget representing an OpenVPN configuration entry.
    ویجت اختصاصی ردیف لیست برای نمایش کانفیگ OpenVPN همراه با برچسب پینگ/تأخیر،
    دکمه ستاره (مورد علاقه) و دکمه ویرایش.
    """
    def __init__(self, filename: str, ovpn_dir: str,
                 favorites: set[str] | None = None,
                 on_favorite_toggled=None,
                 protocols: set[str] | frozenset[str] | None = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.filename: str = filename
        self.ovpn_dir: str = ovpn_dir
        self.on_favorite_toggled = on_favorite_toggled
        self.protocols: frozenset[str] = frozenset(protocols or ())
        is_favorite = bool(favorites and filename in favorites)

        self.box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 8)
        self.box.set_margin_start(10)
        self.box.set_margin_end(8)
        self.box.set_margin_top(4)
        self.box.set_margin_bottom(4)

        # Favorite (star) toggle / دکمه ستاره‌دار کردن کانفیگ
        self.fav_button = Gtk.ToggleButton()
        self.fav_button.set_icon_name(
            "starred-symbolic" if is_favorite else "non-starred-symbolic"
        )
        self.fav_button.add_css_class("flat")
        self.fav_button.add_css_class("server-fav-btn")
        self.fav_button.set_valign(Gtk.Align.CENTER)
        self.fav_button.set_active(is_favorite)
        self.fav_button.set_tooltip_text(
            gettext.gettext("Remove from Favorites") if is_favorite
            else gettext.gettext("Add to Favorites")
        )
        self.fav_button.connect("toggled", self._on_favorite_toggled)

        # File label / نام فایل کانفیگ
        self.label = Gtk.Label.new(filename)
        self.label.set_halign(Gtk.Align.START)
        self.label.set_hexpand(True)
        self.label.set_xalign(0.0)

        # Protocol badge (TCP / UDP) / نشان پروتکل
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

        # Latency label / برچسب نمایش پینگ
        self.latency_label = Gtk.Label.new("")
        self.latency_label.set_halign(Gtk.Align.END)
        self.latency_label.set_margin_end(8)

        # Edit button / دکمه ویرایش فایل کانفیگ
        self.edit_button = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        self.edit_button.set_has_frame(False)
        self.edit_button.set_tooltip_text(gettext.gettext("Edit Configuration"))
        self.edit_button.set_halign(Gtk.Align.END)
        self.edit_button.set_visible(False)
        self.edit_button.add_css_class("btn-no-dec")

        target_file = Path(self.ovpn_dir).joinpath(filename)
        self.edit_button.connect("clicked", lambda w: subprocess.run(["xdg-open", str(target_file)]))

        self.box.append(self.fav_button)
        self.box.append(self.label)
        self.box.append(self.proto_badge)
        self.box.append(self.latency_label)
        self.box.append(self.edit_button)
        self.set_child(self.box)

    def _on_favorite_toggled(self, button: Gtk.ToggleButton):
        """Updates star icon and persists the favorite state."""
        active = button.get_active()
        button.set_icon_name("starred-symbolic" if active else "non-starred-symbolic")
        button.set_tooltip_text(
            gettext.gettext("Remove from Favorites") if active
            else gettext.gettext("Add to Favorites")
        )
        if self.on_favorite_toggled:
            self.on_favorite_toggled(self.filename, active)

    def set_edit_visible(self, visible: bool):
        """Toggles visibility of the inline edit button."""
        self.edit_button.set_visible(visible)


class StorageItem:
    MAIN_WINDOW = "main-window"
    SETTINGS_WINDOW = "settings-window"
    LISTBOX = "listbox"
    LISTBOX_ROWS = "listbox-rows"
    LISTSTORE = "liststore"
    CONFIGS_LIST = "listbox-rows-index"
    FLAG = "flag"


class Settings:
    LAST_CONNECTED = "last-connected"
    LAST_CONNECTED_CURSOR = "last-connected-cursor"
    NOTIFICATIONS = "notifications"
    MANAGER = "manager"
    REQ_AUTH = "req-auth"
    CA = "ca"
    REMOTE = "remote"
    AUTH_USER = "auth-user"
    NM_ACTIVE_UUID = "nm-active-uuid"
    SHOW_FLAG = "show-flag"
    LISTBOX_V_ADJUST = "listbox-v-adjust"
    LAYOUT = "layout"
    DARK_THEME = "dark-theme"
    OPENVPN3_DCO = "openvpn3-dco"
    AUTO_RECONNECT = "auto-reconnect"
    LANGUAGE = "language"
    FAVORITES = "favorite-configs"

    # Keep this list in sync with the GSettings schema keys
    # این فهرست باید با کلیدهای اسکیمای GSettings هماهنگ بماند
    all_settings = [
        "last-connected", "last-connected-cursor", "notifications", "manager",
        "req-auth", "ca", "remote", "auth-user", "nm-active-uuid", "show-flag",
        "listbox-v-adjust", "layout", "dark-theme", "auto-reconnect",
        "favorite-configs", "language", "openvpn3-dco"
    ]


class Base:
    """
    Base controller class providing application metadata, settings access, and notification helpers.
    کلاس پایه ارائه‌دهنده متادیتا، دسترسی به تنظیمات و سیستم ارسال اعلان‌ها.
    """

    def __init__(self):
        metadata_path = os.path.join(os.path.dirname(__file__), "metadata.json")
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.loads(f.read())
        except Exception:
            metadata = {
                "APP_NAME": "eOVPN Pro",
                "APP_ID": "com.github.mahdi-arts.eovpn-pro",
                "APP_VERSION": "1.5",
                "COMMIT": "release",
                "AUTHOR": "Mahdi Bagheban",
                "AUTHOR_MAIL": "info@MahdiArts.ir",
                "AUTHOR_MAIL_SECONDARY": "mehdi.bagheban@gmail.com",
                "AUTHOR_WEBSITE": "https://www.MahdiArts.ir",
                "AUTHOR_DONATE": "https://www.MahdiArts.ir/donate"
            }

        self.APP_NAME = metadata.get("APP_NAME", "eOVPN Pro")
        self.APP_ID = metadata.get("APP_ID", "com.github.mahdi-arts.eovpn-pro")
        self.APP_VERSION = metadata.get("APP_VERSION", "1.5")
        self.APP_COMMIT = metadata.get("COMMIT", "release")
        self.AUTHOR = metadata.get("AUTHOR", "Mahdi Bagheban")
        self.AUTHOR_MAIL = metadata.get("AUTHOR_MAIL", "info@MahdiArts.ir")
        self.AUTHOR_MAIL_SECONDARY = metadata.get("AUTHOR_MAIL_SECONDARY", "mehdi.bagheban@gmail.com")
        self.AUTHOR_WEBSITE = metadata.get("AUTHOR_WEBSITE", "https://www.MahdiArts.ir")
        self.AUTHOR_DONATE = metadata.get("AUTHOR_DONATE", "https://www.MahdiArts.ir/donate")

        self.TRANSLATORS = {}
        self.EOVPN_SECRET_SCHEMA = EOVPN_SECRET_SCHEMA

        self.EOVPN_CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "eovpn")
        self.EOVPN_OVPN_CONFIG_DIR = os.path.join(self.EOVPN_CONFIG_DIR, "CONFIGS")
        self.EOVPN_GRESOURCE_PREFIX = "/com/github/mahdi-arts/eovpn-pro"
        self.EOVPN_CSS = self.EOVPN_GRESOURCE_PREFIX + "/css/main.css"
        self.SETTING = Settings()
        self.__settings = Gio.Settings.new(self.APP_ID)

    def set_session_password(self, password: str | None):
        """Stores password securely in volatile RAM session cache only."""
        if password:
            _session_secrets["auth_password"] = password
        else:
            _session_secrets.pop("auth_password", None)

    def get_session_password(self) -> str | None:
        """Retrieves in-memory session password."""
        return _session_secrets.get("auth_password", None)

    def get_builder(self, ui_resource_name: str) -> Gtk.Builder:
        if ui_resource_name not in _builder_record:
            builder = Gtk.Builder()
            builder.add_from_resource(self.EOVPN_GRESOURCE_PREFIX + "/ui/" + ui_resource_name)
            _builder_record[ui_resource_name] = builder
            return builder
        return _builder_record[ui_resource_name]

    def store(self, item: str, obj: object):
        _storage_record[item] = obj

    def retrieve(self, item: str) -> object:
        return _storage_record.get(item)

    def send_connected_notification(self):
        if self.get_setting(self.SETTING.NOTIFICATIONS) is False:
            return
        Notify.init(self.APP_ID)
        notif = Notify.Notification.new(
            gettext.gettext("Connected"),
            gettext.gettext("Secure VPN connection established.")
        )
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_resource_at_scale(
                self.EOVPN_GRESOURCE_PREFIX + "/icons/notification_connected.svg",
                128, -1, True
            )
            notif.set_image_from_pixbuf(pixbuf)
        except Exception as e:
            logger.debug("Failed to set notification pixbuf: %s", e)
        notif.show()

    def send_disconnected_notification(self):
        if self.get_setting(self.SETTING.NOTIFICATIONS) is False:
            return
        Notify.init(self.APP_ID)
        notif = Notify.Notification.new(
            gettext.gettext("Disconnected"),
            gettext.gettext("VPN tunnel disconnected.")
        )
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_resource_at_scale(
                self.EOVPN_GRESOURCE_PREFIX + "/icons/notification_disconnected.svg",
                128, -1, True
            )
            notif.set_image_from_pixbuf(pixbuf)
        except Exception as e:
            logger.debug("Failed to set notification pixbuf: %s", e)
        notif.show()

    def send_error_notification(self, error_message: str):
        if self.get_setting(self.SETTING.NOTIFICATIONS) is False:
            return
        Notify.init(self.APP_ID)
        notif = Notify.Notification.new(gettext.gettext("Connection Error"), error_message)
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_resource_at_scale(
                self.EOVPN_GRESOURCE_PREFIX + "/icons/notification_disconnected.svg",
                128, -1, True
            )
            notif.set_image_from_pixbuf(pixbuf)
        except Exception as e:
            logger.debug("Failed to set notification pixbuf: %s", e)
        notif.show()

    def get_country_pixbuf(self, country_code: str | None) -> GdkPixbuf.Pixbuf:
        code = country_code.lower() if country_code else "uno"
        try:
            return GdkPixbuf.Pixbuf.new_from_resource_at_scale(
                f"{self.EOVPN_GRESOURCE_PREFIX}/country_flags/svg/{code}.svg",
                -1, 128, True
            )
        except Exception:
            return GdkPixbuf.Pixbuf.new_from_resource_at_scale(
                f"{self.EOVPN_GRESOURCE_PREFIX}/country_flags/svg/uno.svg",
                -1, 128, True
            )

    def get_setting(self, key: str):
        try:
            v = self.__settings.get_value(key)
        except Exception as e:
            logger.debug("GSettings key %s not found: %s", key, e)
            return None

        v_type = v.get_type_string()
        if v_type == 'b':
            return v.get_boolean()
        elif v_type == 'i':
            return v.get_int32()
        elif v_type == 's':
            val = v.get_string()
            # "null" is the project's sentinel for an unset string key
            # رشته "null" به‌عنوان نشانگر مقدار تنظیم‌نشده برای کلیدهای متنی است
            return None if val == "null" else val
        elif v_type == "d":
            return v.get_double()
        elif v_type == "as":
            return list(v.get_strv())
        return None

    def set_setting(self, key: str, value):
        if value is None:
            self.__settings.reset(key)
            return

        g_value = None
        if isinstance(value, bool):
            g_value = GLib.Variant.new_boolean(value)
        elif isinstance(value, int):
            g_value = GLib.Variant.new_int32(value)
        elif isinstance(value, float):
            g_value = GLib.Variant.new_double(value)
        elif isinstance(value, str):
            g_value = GLib.Variant.new_string(value)
        elif isinstance(value, (list, tuple)):
            g_value = GLib.Variant.new_strv([str(v) for v in value])

        if g_value is not None:
            try:
                self.__settings.set_value(key, g_value)
            except Exception as e:
                logger.error("Failed to set setting %s: %s", key, e)

    def reset_all_settings(self):
        for key in self.SETTING.all_settings:
            try:
                _settings_backup[key] = self.__settings.get_value(key)
                self.__settings.reset(key)
            except Exception:
                pass
        self.__settings.sync()

    def undo_reset_settings(self):
        for k, v in _settings_backup.items():
            try:
                self.__settings.set_value(k, v)
            except Exception:
                pass
        self.__settings.sync()

    def reset_paths(self):
        """Wipes and recreates the managed configs directory."""
        shutil.rmtree(self.EOVPN_OVPN_CONFIG_DIR, ignore_errors=True)
        os.makedirs(self.EOVPN_OVPN_CONFIG_DIR, exist_ok=True)

    def get_favorites(self) -> set[str]:
        """
        Returns the set of favorite configuration filenames.
        بازگرداندن مجموعه نام کانفیگ‌های نشان‌شده (مورد علاقه).
        """
        favs = self.get_setting(self.SETTING.FAVORITES)
        return set(favs) if favs else set()

    def toggle_favorite(self, filename: str, favorite: bool):
        """
        Adds or removes a configuration from the favorites list.
        افزودن یا حذف یک کانفیگ به فهرست کانفیگ‌های مورد علاقه.
        """
        favs = self.get_favorites()
        if favorite:
            favs.add(filename)
        else:
            favs.discard(filename)
        self.set_setting(self.SETTING.FAVORITES, sorted(favs))

    def _notify_list_changed(self):
        """Fires the optional list-change hook (used by MainWindow counters)."""
        hook = self.retrieve("on_list_changed")
        if hook is not None:
            try:
                hook()
            except Exception as e:
                logger.debug("List-changed hook failed: %s", e)

    def load_only(self) -> int | None:
        self.store("latency_labels", {})
        self.store("proto_cache", {})

        # Read favorites once per (re)load to avoid repeated GSettings access
        # خواندن یک‌باره لیست موردعلاقه‌ها در هر بار بارگذاری جهت کاهش دسترسی به GSettings
        favorites = self.get_favorites()

        def widget_factory(item):
            filename = str(item)
            proto_cache = self.retrieve("proto_cache")
            if not isinstance(proto_cache, dict):
                proto_cache = {}
                self.store("proto_cache", proto_cache)
            if filename not in proto_cache:
                proto_cache[filename] = parse_ovpn_protocols(
                    str(Path(self.EOVPN_OVPN_CONFIG_DIR).joinpath(filename))
                )
            row = ConfigRow(
                filename,
                self.EOVPN_OVPN_CONFIG_DIR,
                favorites=favorites,
                on_favorite_toggled=self.retrieve("favorite_toggled_cb"),
                protocols=proto_cache[filename],
            )

            latency_dict = self.retrieve("latency_labels")
            if isinstance(latency_dict, dict):
                latency_dict[filename] = row.latency_label

            rows_list = self.retrieve(StorageItem.LISTBOX_ROWS)
            if isinstance(rows_list, list):
                rows_list.append(row)
            return row

        box = self.retrieve(StorageItem.LISTBOX)
        if not box:
            return 0

        try:
            configs = [f for f in os.listdir(self.EOVPN_OVPN_CONFIG_DIR) if f.endswith(".ovpn")]
            configs.sort()
        except Exception:
            configs = []

        liststore = Gio.ListStore.new(ConfigItem)
        self.store(StorageItem.LISTSTORE, liststore)

        # If a filter model is registered (search/filter feature), bind through it
        # در صورت وجود مدل فیلتر (جستجو/فیلتر)، لیست از طریق آن به ListBox متصل می‌شود
        filter_model = self.retrieve("filter_model")
        if filter_model is not None:
            try:
                filter_model.set_model(liststore)
            except Exception as e:
                logger.debug("Failed to attach filter model: %s", e)
                filter_model = None

        bind_model = filter_model if filter_model is not None else liststore
        box.bind_model(bind_model, widget_factory)

        self.store(StorageItem.CONFIGS_LIST, configs)
        self.store(StorageItem.LISTBOX_ROWS, [])

        for file in configs:
            liststore.append(ConfigItem(file))
        self._notify_list_changed()
        return len(configs)

    def remove_only(self, remove_path: bool = False):
        if remove_path:
            self.reset_paths()
        liststore = self.retrieve(StorageItem.LISTSTORE)
        if liststore and hasattr(liststore, "remove_all"):
            liststore.remove_all()
        self.store(StorageItem.LISTBOX_ROWS, [])
        self.store(StorageItem.CONFIGS_LIST, [])
        self._notify_list_changed()

    def validate_and_load(self, spinner=None, ca_button=None):
        """
        Fetches the configuration source and atomically replaces the configs
        directory, so a failed download never destroys the existing configs.
        دریافت منبع کانفیگ و جایگزینی اتمی دایرکتوری کانفیگ‌ها؛ در صورت خطا،
        کانفیگ‌های قبلی کاربر هرگز از بین نمی‌روند.
        """
        remote_source = self.get_setting(self.SETTING.REMOTE)
        if not remote_source:
            logger.error("Configuration source is empty!")
            return

        def fade_tick(tick):
            if tick.get_opacity() <= 0:
                tick.hide()
                return False
            tick.set_opacity(tick.get_opacity() - 0.05)
            return True

        def glib_func():
            self.remove_only()
            n_added = self.load_only()
            if n_added:
                tick = self.retrieve("settings_tick")
                if tick:
                    tick.set_opacity(1.0)
                    tick.show()
                    GLib.timeout_add(25, fade_tick, tick)
            if spinner is not None:
                spinner.stop()
            return False

        def dispatch():
            staging_dir = self.EOVPN_OVPN_CONFIG_DIR + ".staging"
            backup_dir = self.EOVPN_OVPN_CONFIG_DIR + ".old"
            try:
                # Download into a staging directory first
                # دانلود ابتدا در یک دایرکتوری موقت (مرحله‌ای)
                shutil.rmtree(staging_dir, ignore_errors=True)
                cert = download_remote_to_destination(remote_source, staging_dir)

                # Atomic swap: configs -> .old, staging -> configs
                # جابجایی اتمی: کانفیگ فعلی به .old و دایرکتوری موقت به جای آن
                shutil.rmtree(backup_dir, ignore_errors=True)
                if os.path.exists(self.EOVPN_OVPN_CONFIG_DIR):
                    os.rename(self.EOVPN_OVPN_CONFIG_DIR, backup_dir)
                os.rename(staging_dir, self.EOVPN_OVPN_CONFIG_DIR)
                shutil.rmtree(backup_dir, ignore_errors=True)

                if cert:
                    ca_path = os.path.join(self.EOVPN_OVPN_CONFIG_DIR, os.path.basename(cert[-1]))
                    self.set_setting(self.SETTING.CA, ca_path)
                    if ca_button is not None:
                        ca_button.set_label(cert[-1])
            except Exception as e:
                logger.error("Download failed: %s", e)
                shutil.rmtree(staging_dir, ignore_errors=True)
            finally:
                GLib.idle_add(glib_func)

        thread = threading.Thread(target=dispatch)
        thread.daemon = True
        thread.start()
        if spinner is not None:
            spinner.start()
