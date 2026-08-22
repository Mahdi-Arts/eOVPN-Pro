"""
Reproducible local build-and-run helper for eOVPN-Pro.
ابزار بازتولیدپذیر ساخت و اجرای محلی eOVPN-Pro.

The helper checks every subprocess result and defaults to the production
NetworkManager-only feature set. Set ``EOVPN_BUILD_OPENVPN3=1`` to build the
optional OpenVPN 3 binding.
این ابزار نتیجه همه فرایندها را بررسی می‌کند و به‌صورت پیش‌فرض مانند نسخه اصلی
فقط NetworkManager را می‌سازد. برای OpenVPN 3 متغیر یادشده را روی 1 قرار دهید.
"""

from __future__ import annotations

import gettext
import locale
import os
import pathlib
import shutil
import subprocess
import sys

from gi.repository import Gio

APP_ID = "io.github.Mahdi_Arts.eOVPN_Pro"
BUILD_OPENVPN3 = os.getenv("EOVPN_BUILD_OPENVPN3") == "1"
ROOT = pathlib.Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"

sys.path.insert(1, str(ROOT))
os.environ["GSETTINGS_SCHEMA_DIR"] = str(ROOT / "data")
os.environ.setdefault("G_MESSAGES_DEBUG", "eovpn")


def run_checked(*command: str) -> None:
    """Runs one command and stops on failure / اجرای دستور و توقف در خطا."""
    subprocess.run(command, cwd=ROOT, check=True)


def build() -> None:
    """Creates a clean Meson build / ساخت تمیز پروژه با Meson."""
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    generated_enums = ROOT / "subprojects/openvpn3/enums.h"
    generated_enums.unlink(missing_ok=True)
    run_checked(
        "meson",
        "setup",
        str(BUILD_DIR),
        "-Dprefix=/usr",
        f"-Dopenvpn3={'true' if BUILD_OPENVPN3 else 'false'}",
    )
    run_checked("ninja", "-C", str(BUILD_DIR))
    run_checked("meson", "test", "-C", str(BUILD_DIR), "--print-errorlogs")


def copy_bindings() -> None:
    """Copies build-tree bindings beside Python sources / کپی بایندینگ‌ها کنار سورس پایتون."""
    targets = [
        (
            BUILD_DIR / "subprojects/networkmanager/libeovpn_nm.so",
            ROOT / "eovpn/backend/networkmanager/libeovpn_nm.so",
        ),
        (
            BUILD_DIR / "subprojects/networkmanager/_libeovpn_nm.so",
            ROOT / "eovpn/backend/networkmanager/_libeovpn_nm.so",
        ),
        (BUILD_DIR / "eovpn/metadata.json", ROOT / "eovpn/metadata.json"),
    ]
    if BUILD_OPENVPN3:
        targets.extend(
            [
                (
                    BUILD_DIR / "subprojects/openvpn3/libopenvpn3.so",
                    ROOT / "eovpn/backend/openvpn3/libopenvpn3.so",
                ),
                (
                    BUILD_DIR / "subprojects/openvpn3/_libopenvpn3.so",
                    ROOT / "eovpn/backend/openvpn3/_libopenvpn3.so",
                ),
            ]
        )
    for source, destination in targets:
        shutil.copy2(source, destination)


def configure_language() -> None:
    """Configures gettext for system/English/Persian / تنظیم gettext برای زبان انتخابی."""
    try:
        language = Gio.Settings.new(APP_ID).get_string("language")
    except Exception:
        language = "system"
    if language != "system":
        os.environ["LANGUAGE"] = language
    locale.bindtextdomain("eovpn", str(BUILD_DIR / "po"))
    gettext.bindtextdomain("eovpn", str(BUILD_DIR / "po"))
    gettext.textdomain("eovpn")


def main() -> int:
    build()
    copy_bindings()
    run_checked("glib-compile-schemas", str(ROOT / "data"))
    configure_language()

    resource_path = BUILD_DIR / "data" / f"{APP_ID}.gresource"
    Gio.resources_register(Gio.resource_load(str(resource_path)))
    if "--debug" not in sys.argv:
        sys.argv.extend(["--debug", "DEBUG"])

    from eovpn.application import launch_eovpn

    return launch_eovpn()


if __name__ == "__main__":
    sys.exit(main())
