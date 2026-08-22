"""
eOVPN-Pro Metadata Helper
کمک‌خوان متادیتای eOVPN-Pro

Loads the build-time ``metadata.json`` without importing GTK, so pure modules
(``utils``, ``ip_lookup``, …) can embed the real application version in HTTP
headers instead of a hard-coded string that drifts out of sync on every bump.

فایل ``metadata.json`` زمان ساخت را بدون ایمپورت GTK بارگذاری می‌کند تا ماژول‌های
خالص بتوانند نسخهٔ واقعی برنامه را به‌جای رشتهٔ هاردکد (که با هر تغییر نسخه از
هماهنگی خارج می‌شود) در هدرهای HTTP قرار دهند.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

# Fallback values used when metadata.json has not been generated yet
# (i.e. running straight from the source tree without a Meson build).
# مقادیر جایگزین برای زمانی که metadata.json هنوز تولید نشده است
# (اجرای مستقیم از درخت منبع بدون ساخت Meson).
_FALLBACK_METADATA: dict[str, str] = {
    "APP_NAME": "eOVPN Pro",
    "APP_ID": "com.github.mahdi-arts.eovpn-pro",
    "APP_VERSION": "dev",
    "COMMIT": "local_build",
    "AUTHOR": "Mahdi Bagheban",
    "AUTHOR_MAIL": "info@MahdiArts.ir",
    "AUTHOR_MAIL_SECONDARY": "mehdi.bagheban@gmail.com",
    "AUTHOR_WEBSITE": "https://www.MahdiArts.ir",
    "AUTHOR_DONATE": "https://www.MahdiArts.ir/donate",
}


@lru_cache(maxsize=1)
def load_metadata() -> dict[str, str]:
    """
    Reads and caches the generated ``metadata.json`` next to this module.

    خواندن و کش کردن فایل تولیدشدهٔ metadata.json کنار همین ماژول.
    """
    metadata_path = os.path.join(os.path.dirname(__file__), "metadata.json")
    try:
        with open(metadata_path, encoding="utf-8") as handle:
            data = json.loads(handle.read())
        if isinstance(data, dict):
            return {str(key): str(value) for key, value in data.items()}
    except (OSError, ValueError, TypeError):
        pass
    return dict(_FALLBACK_METADATA)


def app_version(default: str = "dev") -> str:
    """
    Returns the application version reported by the build system.

    بازگرداندن نسخهٔ برنامه که سیستم ساخت گزارش می‌کند.
    """
    return load_metadata().get("APP_VERSION") or default
