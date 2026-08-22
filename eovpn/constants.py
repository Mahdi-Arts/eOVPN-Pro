"""
eOVPN-Pro shared application constants.
ثابت‌های مشترک برنامه eOVPN-Pro.

Keeping identity and security-sensitive values in one module prevents drift
between the UI, backends, packaging metadata, and migration code.
نگهداری شناسه‌ها و مقادیر حساس امنیتی در یک ماژول، از ناهماهنگی میان رابط
کاربری، بک‌اندها، متادیتای بسته‌بندی و کد مهاجرت جلوگیری می‌کند.
"""

from __future__ import annotations

APP_ID = "io.github.Mahdi_Arts.eOVPN_Pro"
APP_NAME = "eOVPN Pro"
RESOURCE_PREFIX = "/io/github/Mahdi_Arts/eOVPN_Pro"
SECRET_SCHEMA_ID = APP_ID

# Previous application identifiers are retained only for one-way migration.
# شناسه‌های قبلی فقط برای مهاجرت یک‌طرفه تنظیمات و رمزها نگهداری می‌شوند.
LEGACY_APP_IDS: tuple[str, ...] = (
    "com.github.mahdi-arts.eovpn-pro",
    "com.github.jkotra.eovpn",
)
LEGACY_SECRET_SCHEMA_IDS: tuple[str, ...] = LEGACY_APP_IDS

CONFIG_DIR_NAME = "eovpn"
CONFIGS_DIR_NAME = "CONFIGS"

# NetworkManager profiles created by this application are tracked by UUID.
# پروفایل‌های ساخته‌شده توسط برنامه فقط با UUID خود برنامه مدیریت می‌شوند.
NM_PROFILE_LABEL_PREFIX = "eOVPN Pro"

# Finite D-Bus calls avoid freezing the GTK main loop indefinitely.
# محدودیت زمانی فراخوانی D-Bus از توقف نامحدود حلقه اصلی GTK جلوگیری می‌کند.
DBUS_TIMEOUT_MS = 10_000
