"""
eOVPN-Pro Local Debug Launcher
اجرای محلی و دیباگ eOVPN-Pro

Builds the native CFFI bindings with Meson/Ninja and launches the app from the
source tree (no system installation required).
کتابخانه‌های بومی CFFI را با Meson/Ninja می‌سازد و برنامه را بدون نیاز به نصب
سیستمی، مستقیم از درخت منبع اجرا می‌کند.
"""

import os
import pathlib
import shutil
import subprocess
import sys

from gi.repository import Gio

# Set to False to build without the OpenVPN 3 backend
# برای ساخت بدون بک‌اند OpenVPN 3 مقدار را False کنید
OPENVPN3 = True

try:
    import openvpn3  # noqa: F401  (presence check only / فقط بررسی وجود)
except ImportError:
    OPENVPN3 = False

APP_NAME = "com.github.mahdi-arts.eovpn-pro"

sys.path.insert(1, os.getcwd())
sys.path.insert(1, os.getcwd() + "/eovpn/")
os.environ["GSETTINGS_SCHEMA_DIR"] = "data/"
os.environ["G_MESSAGES_DEBUG"] = "eovpn"


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
