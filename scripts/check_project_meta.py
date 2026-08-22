#!/usr/bin/env python3
"""
eOVPN-Pro Project Metadata Consistency Checker
بررسی‌کننده یکپارچگی متادیتای پروژه eOVPN-Pro

Verifies that the project version is in sync across packaging metadata,
that the GSettings schema keys match ``Settings.all_settings``, and that
every gresource entry exists on disk. Exits non-zero on any mismatch so it
can run in CI.
بررسی می‌کند که نسخه پروژه در همه فایل‌های بسته‌بندی هماهنگ باشد، کلیدهای
اسکیمای GSettings با فهرست Settings.all_settings یکسان باشند و همه ورودی‌های
gresource روی دیسک موجود باشند. در صورت هر ناهماهنگی با کد خروجی غیرصفر
تمام می‌شود تا در CI قابل استفاده باشد.
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
        ERRORS.append(
            f"debian/changelog version {deb_ver.group(1) if deb_ver else '?'} != {canonical}"
        )

    for spec_path in (ROOT / "dist" / "rpm" / "eovpn-pro.spec",):
        text = spec_path.read_text(encoding="utf-8")
        spec_ver = re.search(r"^Version:\s*([0-9.]+)", text, re.MULTILINE)
        if not spec_ver or spec_ver.group(1) != canonical:
            ERRORS.append(f"{spec_path.name} Version != {canonical}")

    metainfo = ROOT / "data" / "com.github.mahdi-arts.eovpn-pro.metainfo.xml"
    text = metainfo.read_text(encoding="utf-8")
    release = re.search(r'<release version="([0-9][^"]*)"', text)
    if not release or not release.group(1).startswith(canonical):
        ERRORS.append(f"metainfo.xml latest release != {canonical}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if f"version-{canonical}" not in readme:
        ERRORS.append(f"README.md version badge != {canonical}")


def check_schema_sync() -> None:
    """Checks GSettings keys against Settings.all_settings in eovpn_base.py."""
    schema = ROOT / "data" / "com.github.mahdi-arts.eovpn-pro.gschema.xml"
    text = schema.read_text(encoding="utf-8")
    schema_keys = set(re.findall(r'<key[^>]*name="([^"]+)"', text))

    base = (ROOT / "eovpn" / "eovpn_base.py").read_text(encoding="utf-8")
    block = re.search(r"all_settings\s*=\s*\[(.*?)\]", base, re.DOTALL)
    if not block:
        ERRORS.append("eovpn_base.py: Settings.all_settings list not found")
        return
    code_keys = set(re.findall(r'"([^"]+)"', block.group(1)))

    if schema_keys != code_keys:
        only_schema = sorted(schema_keys - code_keys)
        only_code = sorted(code_keys - schema_keys)
        ERRORS.append(
            "GSettings schema / Settings.all_settings mismatch: "
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
