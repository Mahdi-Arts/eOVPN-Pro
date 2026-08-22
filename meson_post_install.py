#!/usr/bin/env python3
"""
eOVPN-Pro Meson Post-Install Script
اسکریپت پس از نصب Meson در eOVPN-Pro

Refreshes the icon cache and compiles GSettings schemas after installation.
به‌روزرسانی کش آیکون‌ها و کامپایل اسکیماهای GSettings پس از نصب.
"""

from os import environ, path
from subprocess import call

prefix = environ.get("MESON_INSTALL_PREFIX", "/usr/local")
datadir = path.join(prefix, "share")
destdir = environ.get("DESTDIR", "")

print(datadir)

# Skip cache updates when installing into a staged root (DESTDIR)
# هنگام نصب در مسیر موقت (DESTDIR) کش‌ها به‌روزرسانی نمی‌شوند
if not destdir:
    print("Updating icon cache...")
    call(["gtk-update-icon-cache", "-qtf", path.join(datadir, "icons", "hicolor")])
    print("Installing new Schemas")
    call(["glib-compile-schemas", path.join(datadir, "glib-2.0/schemas")])
