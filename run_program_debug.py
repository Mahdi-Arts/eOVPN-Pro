"""
eOVPN-Pro Local Debug Launcher
اجرای محلی و دیباگ eOVPN-Pro

Builds the native CFFI bindings with Meson/Ninja and launches the app from the
source tree (no system installation required).
کتابخانه‌های بومی CFFI را با Meson/Ninja می‌سازد و برنامه را بدون نیاز به نصب
سیستمی، مستقیم از درخت منبع اجرا می‌کند.

Requirements:
  - A running desktop session (Wayland/X11) with GTK4 and Libadwaita.
  - NetworkManager with openvpn plugin installed.
  - نیازمند یک نشست گرافیکی (Wayland/X11) با GTK4 و Libadwaita.
  - نصب NetworkManager به همراه افزونه openvpn.
"""

import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys

from gi.repository import Gio

# Set to False to build without the OpenVPN 3 backend
# برای ساخت بدون بک‌اند OpenVPN 3 مقدار را False کنید
OPENVPN3 = importlib.util.find_spec("openvpn3") is not None

APP_NAME = "com.github.mahdi-arts.eovpn-pro"

sys.path.insert(1, os.getcwd())
sys.path.insert(1, os.getcwd() + "/eovpn/")
os.environ["GSETTINGS_SCHEMA_DIR"] = "data/"
os.environ["G_MESSAGES_DEBUG"] = "eovpn"


def _check_display() -> None:
    """
    Verifies that a GTK-compatible display server is available.
    بررسی وجود یک نمایش‌گر سازگار با GTK.
    """
    display = os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")
    if not display:
        print(
            "ERROR: No display server detected (neither WAYLAND_DISPLAY nor DISPLAY is set).\n"
            "خطا: هیچ نمایش‌گری یافت نشد (نه WAYLAND_DISPLAY و نه DISPLAY تنظیم نشده است).\n"
            "\n"
            "eOVPN-Pro requires a running desktop session with GTK4 / Libadwaita.\n"
            "eOVPN-Pro نیازمند یک نشست گرافیکی با GTK4 / Libadwaita است.\n"
            "\n"
            "You can still run the offline tests:\n"
            "هنوز می‌توانید تست‌های آفلاین را اجرا کنید:\n"
            "  python3 -m unittest discover -s tests -v\n",
            file=sys.stderr,
        )
        sys.exit(1)


def reset() -> None:
    """Reconfigures and rebuilds the native bindings."""
    subprocess.run(["rm", "-rf", "build"])

    if pathlib.Path("subprojects/openvpn3/enums.h").exists():
        subprocess.run(["rm", "subprojects/openvpn3/enums.h"])

    subprocess.run(["meson", "setup", "build", "-Dprefix=/usr", f"-Dopenvpn3={OPENVPN3}"])
    subprocess.run(["ninja", "-C", "build"])


def copy_libs() -> None:
    """Copies the built shared libraries next to the Python sources."""
    shutil.copyfile(
        "build/subprojects/networkmanager/libeovpn_nm.so",
        "eovpn/backend/networkmanager/libeovpn_nm.so",
    )
    shutil.copyfile(
        "build/subprojects/networkmanager/_libeovpn_nm.so",
        "eovpn/backend/networkmanager/_libeovpn_nm.so",
    )

    if OPENVPN3:
        shutil.copyfile(
            "build/subprojects/openvpn3/libopenvpn3.so",
            "eovpn/backend/openvpn3/libopenvpn3.so",
        )
        shutil.copyfile(
            "build/subprojects/openvpn3/_libopenvpn3.so",
            "eovpn/backend/openvpn3/_libopenvpn3.so",
        )

    shutil.copyfile("build/eovpn/metadata.json", "eovpn/metadata.json")


def main() -> None:
    """Entry point: validates environment, builds, and launches the app."""
    _check_display()
    reset()
    copy_libs()

    from eovpn.application import launch_eovpn

    gre_path = "build/data/com.github.mahdi-arts.eovpn-pro.gresource"
    resource = Gio.resource_load(gre_path)
    subprocess.run(["glib-compile-schemas", "data/"])
    sys.argv.append("--debug")
    sys.argv.append("DEBUG")
    Gio.Resource._register(resource)

    try:
        settings = Gio.Settings.new(APP_NAME)
        lang = settings.get_string("language")
    except Exception:
        lang = "en"

    if lang:
        os.environ["LANGUAGE"] = lang

    launch_eovpn()


if __name__ == "__main__":
    main()
