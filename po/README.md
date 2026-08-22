# Localization / بومی‌سازی

## English

English source strings are the fallback catalogue and `fa.po` contains the
maintained Persian translation. Every UI change must update `fa.po` in the same
commit. Validate completeness and Python format placeholders with:

```bash
python3 tools/check_translations.py
```

Regenerate gettext references during a Meson build with:

```bash
meson setup build
meson compile -C build eovpn-pot eovpn-update-po
```

Poedit may be used for review, but the repository check remains authoritative.

## فارسی

رشته‌های انگلیسی سورس، کاتالوگ جایگزین هستند و ترجمه نگهداری‌شده فارسی در
`fa.po` قرار دارد. هر تغییر رابط کاربری باید در همان Commit ترجمه فارسی را نیز
به‌روزرسانی کند. کامل‌بودن ترجمه و Placeholderهای قالب پایتون با دستور بالا
بررسی می‌شود. برای تولید مجدد Referenceهای gettext نیز از Targetهای Meson بالا
استفاده کنید. استفاده از Poedit برای بازبینی مجاز است، اما کنترل مخزن مرجع نهایی
محسوب می‌شود.
