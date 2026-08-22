#!/usr/bin/env python3
"""
Verify that every literal UI message has a complete Persian translation.
بررسی کامل‌بودن ترجمه فارسی برای همه پیام‌های صریح رابط کاربری.
"""

from __future__ import annotations

import ast
import string
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]


def python_messages() -> set[str]:
    """Extracts gettext literals from application Python / استخراج رشته‌های gettext از پایتون."""
    messages: set[str] = set()
    for path in (ROOT / "eovpn").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            function = node.func
            is_gettext = (
                isinstance(function, ast.Name)
                and function.id in {"_", "gettext"}
            ) or (
                isinstance(function, ast.Attribute)
                and function.attr == "gettext"
            )
            argument = node.args[0]
            if is_gettext and isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                messages.add(argument.value)
    return messages


def ui_messages() -> set[str]:
    """Extracts translatable GtkBuilder properties / استخراج ویژگی‌های قابل ترجمه GtkBuilder."""
    messages: set[str] = set()
    for path in (ROOT / "data/ui").glob("*.ui"):
        for element in ET.parse(path).getroot().iter():
            if element.attrib.get("translatable", "").lower() in {"1", "true", "yes"}:
                if element.text and element.text.strip():
                    messages.add(element.text.strip())
    return messages


def placeholders(value: str) -> tuple[str, ...]:
    """Returns format-field names / بازگرداندن نام Placeholderهای قالب."""
    fields = []
    for _literal, field_name, _format_spec, _conversion in string.Formatter().parse(value):
        if field_name is not None:
            fields.append(field_name)
    return tuple(fields)


def main() -> int:
    required = python_messages() | ui_messages()
    catalogue = polib.pofile(str(ROOT / "po/fa.po"))
    entries = {entry.msgid: entry for entry in catalogue if not entry.obsolete}
    missing = sorted(message for message in required if message not in entries)
    empty = sorted(
        message
        for message in required
        if message in entries and not entries[message].msgstr.strip()
    )
    fuzzy = sorted(entry.msgid for entry in catalogue.fuzzy_entries())
    placeholder_errors = sorted(
        message
        for message in required
        if message in entries
        and entries[message].msgstr
        and placeholders(message) != placeholders(entries[message].msgstr)
    )

    failures = {
        "missing translations / ترجمه مفقود": missing,
        "empty translations / ترجمه خالی": empty,
        "fuzzy translations / ترجمه نامطمئن": fuzzy,
        "placeholder mismatches / ناهماهنگی Placeholder": placeholder_errors,
    }
    failed = False
    for title, values in failures.items():
        if values:
            failed = True
            print(f"{title}:", file=sys.stderr)
            for value in values:
                print(f"  - {value}", file=sys.stderr)
    if failed:
        return 1
    print(f"Persian catalogue complete: {len(required)} required messages / ترجمه کامل")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
