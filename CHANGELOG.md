# Changelog / تاریخچه تغییرات

All notable changes follow [Keep a Changelog](https://keepachangelog.com/) and
semantic versioning. همه تغییرات مهم بر اساس Keep a Changelog و نسخه‌گذاری
معنایی ثبت می‌شوند.

## [Unreleased] / منتشرنشده

### English

- Release artifacts are pending a successful Debian and Flatpak CI run and an
  annotated `v1.5.0` tag.

### فارسی

- فایل‌های انتشار تا عبور موفق ساخت Debian و Flatpak در CI و ایجاد Tag توضیح‌دار
  `v1.5.0` در حالت انتظار هستند.

## [1.5.0] - 2026-08-22

### Security / امنیت

- Scoped NetworkManager operations and signals to eOVPN-owned UUIDs.
- Scoped OpenVPN 3 operations and attention prompts to one owned object path.
- Added private `0700` repositories and `0600` imported profiles/assets.
- Enforced HTTPS-only remote sources, bounded downloads/extraction, duplicate
  detection, symlink rejection, and transactional rollback.
- Changed password persistence to one explicit Secret Service save/clear action.
- Made public IP lookup opt-in, bounded, validated, and free of personal-data logs.

- عملیات و سیگنال‌های NetworkManager به UUIDهای متعلق به eOVPN محدود شدند.
- عملیات و چالش‌های OpenVPN 3 فقط به مسیر شیء متعلق به برنامه محدود شدند.
- مخزن خصوصی `0700` و فایل‌های واردشده `0600` اضافه شدند.
- منبع راه‌دور فقط HTTPS، محدودیت حجم، تشخیص تکرار، رد Symlink و Rollback
  تراکنشی پیاده‌سازی شد.
- ذخیره رمز به اقدام صریح و یک‌باره در Secret Service تغییر کرد.
- استعلام IP عمومی اختیاری، محدود، اعتبارسنجی‌شده و بدون ثبت داده شخصی شد.

### Changed / تغییرات

- Migrated the application ID to `io.github.Mahdi_Arts.eOVPN_Pro` with one-way
  settings and keyring compatibility.
- Replaced bundled third-party flags/icons with original application artwork,
  standard symbolic icons, and Unicode country indicators.
- Distinguish finite TCP RTT, measured-offline TCP, and unmeasured UDP endpoints.
- Added GTK 4.6-compatible confirmations, a secure challenge dialog, status
  feedback, backend switching guards, and reconnect timer cancellation.
- Added active CI, Debian source/binary packaging, Flatpak staging, tests,
  validation, checksums, and release documentation.

- شناسه برنامه همراه مهاجرت یک‌طرفه تنظیمات و Keyring تغییر کرد.
- پرچم‌ها و آیکون‌های شخص ثالث با اثر اصلی، آیکون نمادین و پرچم یونیکد جایگزین شدند.
- RTT معتبر TCP، TCP آفلاین و UDP سنجیده‌نشده از یکدیگر تفکیک شدند.
- تأیید سازگار GTK 4.6، پنجره امن چالش، بازخورد وضعیت، محافظ تعویض بک‌اند و لغو
  Timer اتصال مجدد اضافه شد.
- CI فعال، بسته‌بندی Debian، آماده‌سازی Flatpak، تست، اعتبارسنجی، Checksum و
  مستندات انتشار اضافه شدند.

## Attribution / انتساب

This project is a maintained fork of
[`jkotra/eOVPN`](https://github.com/jkotra/eOVPN), originally created by
Jagadeesh Kotra, with subsequent work by Mahdi Bagheban and all contributors.
این پروژه فورک نگهداری‌شده eOVPN اثر اولیه Jagadeesh Kotra است و توسعه‌های بعدی
توسط مهدی باغبان و سایر مشارکت‌کنندگان انجام شده است.
