#!/usr/bin/env python3
"""
eOVPN-Pro Project Metadata Consistency Checker
بررسی‌کننده یکپارچگی متادیتای پروژه eOVPN-Pro

Verifies that the project version is in sync across packaging metadata
(Meson, Debian changelog, RPM spec, PKGBUILD/.SRCINFO, AppImage script,
AppStream metainfo and the README badge), that the GSettings schema keys match
the ``Settings`` class in ``eovpn_base.py``, and that every gresource entry
exists on disk. Exits non-zero on any mismatch so it can run in CI.

بررسی می‌کند که نسخه پروژه در همه فایل‌های بسته‌بندی هماهنگ باشد، کلیدهای
اسکیمای GSettings با کلاس Settings در eovpn_base.py یکسان باشند و همه ورودی‌های
gresource روی دیسک موجود باشند. در صورت هر ناهماهنگی با کد خروجی غیرصفر تمام
می‌شود تا در CI قابل استفاده باشد.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERRORS: list[str] = []


def version_from_meson() -> str:
    """Reads the canonical version from meson.build."""
    text = (ROOT / "meson.build").read_text(encoding="utf-8")
    match = re.search(r"version:\s*'([0-9]+\.[0-9]+(?:\.[0-9]+)?)'", text)
    if not match:
        ERRORS.append("meson.build: project version not found")
        return ""
    return match.group(1)


def check_versions(canonical: str) -> None:
    """Checks that packaging files carry the same version."""
    deb_changelog = ROOT / "debian" / "changelog"
    first_line = deb_changelog.read_text(encoding="utf-8").splitlines()[0]
    deb_ver = re.search(r"\(([0-9][^)]*)\)", first_line)
    if not deb_ver or not deb_ver.group(1).startswith(canonical):
        ERRORS.append(f"debian/changelog version {deb_ver.group(1) if deb_ver else '?'} != {canonical}")

    for spec_path in (ROOT / "dist" / "rpm" / "eovpn-pro.spec",):
        text = spec_path.read_text(encoding="utf-8")
        spec_ver = re.search(r"^Version:\s*([0-9.]+)", text, re.MULTILINE)
        if not spec_ver or spec_ver.group(1) != canonical:
            ERRORS.append(f"{spec_path.name} Version != {canonical}")

    pkgbuild = ROOT / "dist" / "arch" / "PKGBUILD"
    text = pkgbuild.read_text(encoding="utf-8")
    pkg_ver = re.search(r"^pkgver=([0-9.]+)$", text, re.MULTILINE)
    if not pkg_ver or pkg_ver.group(1) != canonical:
        ERRORS.append(f"PKGBUILD pkgver != {canonical}")

    srcinfo = ROOT / "dist" / "arch" / ".SRCINFO"
    text = srcinfo.read_text(encoding="utf-8")
    src_ver = re.search(r"^\tpkgver = ([0-9.]+)$", text, re.MULTILINE)
    if not src_ver or src_ver.group(1) != canonical:
        ERRORS.append(f".SRCINFO pkgver != {canonical}")

    appimage_script = ROOT / "dist" / "appimage" / "build-appimage.sh"
    text = appimage_script.read_text(encoding="utf-8")
    ai_ver = re.search(r'VERSION="\$\{VERSION:-([0-9.]+)\}"', text)
    if not ai_ver or ai_ver.group(1) != canonical:
        ERRORS.append(f"build-appimage.sh default VERSION != {canonical}")

    metadata_template = ROOT / "eovpn" / "metadata.json.in"
    text = metadata_template.read_text(encoding="utf-8")
    if '"@VERSION@"' not in text:
        ERRORS.append("eovpn/metadata.json.in: @VERSION@ placeholder missing")

    metainfo = ROOT / "data" / "com.github.mahdi-arts.eovpn-pro.metainfo.xml"
    text = metainfo.read_text(encoding="utf-8")
    release = re.search(r'<release version="([0-9][^"]*)"', text)
    if not release or not release.group(1).startswith(canonical):
        ERRORS.append(f"metainfo.xml latest release != {canonical}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if f"version-{canonical}" not in readme:
        ERRORS.append(f"README.md version badge != {canonical}")


def settings_keys_from_source() -> set[str]:
    """
    Extracts the GSettings key names from the ``Settings`` class body.

    استخراج نام کلیدهای GSettings از بدنه کلاس Settings.
    """
    text = (ROOT / "eovpn" / "eovpn_base.py").read_text(encoding="utf-8")
    for chunk in re.split(r"\nclass ", text):
        if not chunk.startswith("Settings"):
            continue
        pairs = re.findall(r'^\s+([A-Z][A-Z0-9_]*) = "([^"]+)"', chunk, re.MULTILINE)
        return {value for _name, value in pairs}
    ERRORS.append("eovpn_base.py: class Settings not found")
    return set()


def check_schema_sync() -> None:
    """Checks GSettings keys against the Settings class in eovpn_base.py."""
    schema = ROOT / "data" / "com.github.mahdi-arts.eovpn-pro.gschema.xml"
    text = schema.read_text(encoding="utf-8")
    schema_keys = set(re.findall(r'<key[^>]*name="([^"]+)"', text))

    code_keys = settings_keys_from_source()

    if schema_keys != code_keys:
        only_schema = sorted(schema_keys - code_keys)
        only_code = sorted(code_keys - schema_keys)
        ERRORS.append(
            "GSettings schema / Settings class mismatch: "
            f"only-in-schema={only_schema} only-in-code={only_code}"
        )


def check_gresource_files() -> None:
    """Checks that every gresource entry exists under data/."""
    xml = (ROOT / "data" / "eovpn.gresource.xml").read_text(encoding="utf-8")
    entries = re.findall(r"<file>([^<]+)</file>", xml)
    missing = [e for e in entries if not (ROOT / "data" / e).exists()]
    if missing:
        ERRORS.append(f"gresource entries missing on disk: {missing}")


def main() -> int:
    canonical = version_from_meson()
    if canonical:
        check_versions(canonical)
    check_schema_sync()
    check_gresource_files()

    if ERRORS:
        print("❌ eOVPN-Pro metadata checks FAILED:", file=sys.stderr)
        for err in ERRORS:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"✅ All metadata checks passed (version {canonical or 'unknown'}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
