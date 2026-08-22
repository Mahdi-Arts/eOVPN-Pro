# ⚡ eOVPN-Pro

<div align="center">
    <img src="static/window_connected_with_flag.png" alt="eOVPN-Pro" width="600">
</div>

<div align="center">

[![Repository](https://img.shields.io/badge/GitHub-Mahdi--Arts%2FeOVPN--Pro-181717?logo=github)](https://github.com/Mahdi-Arts/eOVPN-Pro)
[![Version](https://img.shields.io/badge/version-1.5.0-3E8914)](https://github.com/Mahdi-Arts/eOVPN-Pro/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/Mahdi-Arts/eOVPN-Pro/ci.yml?branch=master&label=CI&logo=githubactions&logoColor=white)](https://github.com/Mahdi-Arts/eOVPN-Pro/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/actions/workflow/status/Mahdi-Arts/eOVPN-Pro/release.yml?label=Release&logo=githubactions&logoColor=white)](https://github.com/Mahdi-Arts/eOVPN-Pro/actions/workflows/release.yml)
[![Packaging](https://img.shields.io/badge/Packages-.deb%20%7C%20.rpm%20%7C%20.pkg.tar.zst%20%7C%20AppImage%20%7C%20Flatpak-blue)](PACKAGING.md)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE)

</div>

---

**eOVPN-Pro** is an advanced, high-performance, and feature-rich OpenVPN configuration manager built with GTK4 and Libadwaita. It is engineered to provide unparalleled speed, real-time bandwidth insight, robust security hardening, and stable connectivity features for Linux users.

**eOVPN-Pro** یک مدیریت‌کننده پیشرفته، با کارایی بالا و مجهز برای کانفیگ‌های OpenVPN است که با GTK4 و Libadwaita طراحی شده است. این نرم‌افزار به طور ویژه برای ارائه حداکثر سرعت شبکه، مانیتورینگ زنده ترافیک، ارتقای استانداردهای امنیتی و اتصال پایدار برای کاربران لینوکس مهندسی و پیاده‌سازی شده است.

---

## ✨ Pro Features (امکانات نسخه حرفه‌ای)

- 🇮🇷 **Full Persian (Farsi) Localization & RTL Support (ترجمه کامل به زبان فارسی و پشتیبانی از راست‌به‌چپ)**:
  - Full Persian localization with dynamic language switching (English/Persian) directly from the primary menu, along with native Right-to-Left (RTL) layout switching.
  - پشتیبانی کامل از زبان فارسی به همراه چیدمان راست‌به‌چپ (RTL) استاندارد و قابلیت تغییر پویای زبان بین انگلیسی و فارسی از منوی اصلی برنامه.

- 📈 **Redesigned Connection Details Card (بازطراحی کادر جزئیات اتصال)**:
  - Features a fixed-size card container using symbolic icons and monospace numbers, completely eliminating layout resizing and window jittering when connection speed fluctuates.
  - دارای کادر ثابت و بسیار مدرن با ابعاد فیکس با استفاده از آیکون‌های سمبلیک و فونت‌های مونو‌اسپیس لرزش‌گیر، جهت ممانعت کامل از هرگونه جابجایی اندازه پنجره در هنگام نوسانات سرعت اینترنت.

- ⚙️ **Optimized Backend & OpenVPN 3 DCO (بهینه‌سازی تنظیمات بک‌اند و فعال‌سازی مستقیم DCO)**:
  - Native Libadwaita ListBox look with a direct switch for OpenVPN 3 Data Channel Offload (DCO) to boost data speeds and reduce CPU overhead.
  - بازطراحی تب تنظیمات بک‌اند و افزودن دکمه کنترل شتاب‌دهنده فوق‌سریع OpenVPN 3 DCO (برون‌سپاری داده به هسته لینوکس) جهت بهینه‌سازی سرعت دانلود و ترافیک و کاهش چشمگیر بار پردازنده.

- ⚡ **Concurrent TCP Speed Test (تست سرعت موازی و همزمان)**:
  - Multi-threaded worker pools test socket-level latency to all remote endpoints within `.ovpn` files concurrently in under 2 seconds.
  - استخراج تمامی آدرس‌ها و پورت‌های مقصد از فایل‌های کانفیگ و انجام تست دست‌دهی پروتکل TCP به صورت چندنخی و کاملاً موازی در کمتر از ۲ ثانیه بدون افت فریم در برنامه.

- 🔄 **Dynamic Latency Sorting & Cascading Auto-Connect (مرتب‌سازی داینامیک و اتصال آبشاری)**:
  - Instantly sorts your VPN configuration list from lowest to highest latency, moving failed servers to the bottom automatically. **Connect Fastest** then walks the current sorted/filtered list (including the TCP/UDP filter) and tries each handshake with an adaptive timeout, switching to the next server on failure (`Ctrl+Shift+C`).
  - مرتب‌سازی آنی لیست کانفیگ‌ها از سریع‌ترین به سنگین‌ترین. دکمه **اتصال به سریع‌ترین** از اولین سرورِ لیستِ مرتب و فیلترشده (از جمله فیلتر TCP/UDP) تلاش می‌کند و در صورت شکست دست‌دهی، با تایم‌اوت تطبیقی به سرور بعدی می‌رود (`Ctrl+Shift+C`).

- 🔎 **Live Search, Filter & Favorites (جستجوی زنده، فیلتر هوشمند و ستاره‌دار کردن سرورها)**:
  - Real-time server search (`Ctrl+F`), smart filtering (All / Favorites / Online / Offline), TCP/UDP protocol filter, star-marked favorite servers with persistent storage, and a live visible/total counter.
  - جستجوی زنده سرورها (`Ctrl+F`)، فیلتر هوشمند (همه / مورد علاقه‌ها / آنلاین / آفلاین)، فیلتر پروتکل TCP/UDP، نشان‌کردن سرورهای محبوب با ستاره و ذخیره دائمی آن‌ها، به همراه شمارنده زنده تعداد سرورهای نمایش‌داده‌شده.

- 📊 **Real-time Bandwidth Monitor (نمایشگر زنده پهنای باند و ترافیک)**:
  - Monitors and displays live download speed, upload speed, and total traffic usage from `/proc/net/dev` once connected.
  - مانیتورینگ زنده و نمایش گرافیکی نرخ دانلود، آپلود و میزان کل مصرف ترافیک اینترنت کارت شبکه VPN به صورت زنده و ثانیه‌ای.

- 🛡️ **Security Hardened Architecture (معماری امن و محافظت‌شده)**:
  - Zero plaintext password leakage into disk/dconf (GNOME Keyring with volatile RAM fallback + agent-owned NetworkManager secrets), secure temporary file generation (`0o600` permissions), Zip-Slip path traversal protection, zip-bomb/size caps, config import audit for executable OpenVPN directives, and encrypted HTTPS IP lookups.
  - عدم ذخیره متن خام رمز عبور روی دیسک، ایجاد ایمن فایل‌های موقت با پرمیشن `0600`، جلوگیری از آسیب‌پذیری‌های فایل فشرده (Zip-Slip) و بمب فشرده، ممیزی کانفیگ‌های واردشده از نظر دایرکتیوهای اجرایی و استعلام امن موقعیت مکانی از طریق پروتکل HTTPS.

- 🔌 **Auto-Reconnect (اتصال مجدد خودکار)**:
  - Detects unexpected connection drops and automatically schedules an immediate reconnect attempt within 3 seconds.
  - شناسایی هوشمند قطعی‌های ناگهانی فیلترشکن و اقدام خودکار جهت اتصال مجدد در ۳ ثانیه.

- 📁 **Local Folder & ZIP Import (وارد کردن دسته‌جمعی و پوشه‌ای کانفیگ‌ها)**:
  - Supports importing VPN configurations directly from a local folder path in addition to ZIP archives.
  - امکان وارد کردن مستقیم فایل‌های کانفیگ از یک پوشه در سیستم یا فایل‌های فشرده ZIP.

---

## 🛠️ Installation & Execution (نصب و اجرا)

Every release publishes prebuilt packages plus a `SHA256SUMS` manifest on the
[Releases page](https://github.com/Mahdi-Arts/eOVPN-Pro/releases).
هر انتشار، بسته‌های آمادهٔ نصب به همراه فایل `SHA256SUMS` را در صفحهٔ Releases قرار می‌دهد.

```bash
# Verify what you downloaded before installing / راستی‌آزمایی فایل دانلودشده پیش از نصب
sha256sum -c SHA256SUMS --ignore-missing
```

### Option 1: Debian / Ubuntu (`.deb`) — *Recommended (پیشنهادی)*
```bash
sudo apt install ./eovpn-pro_1.5.0-1_amd64.deb
```

---

### Option 2: Fedora / RHEL / openSUSE (`.rpm`)
```bash
sudo dnf install ./eovpn-pro-1.5.0-1.x86_64.rpm
```

---

### Option 3: Arch Linux / Manjaro (`.pkg.tar.zst`)
```bash
# A) Install the prebuilt package / نصب بستهٔ آماده
sudo pacman -U eovpn-pro-1.5.0-1-x86_64.pkg.tar.zst

# B) Or build it yourself from the repository / یا ساخت از روی مخزن
git clone https://github.com/Mahdi-Arts/eOVPN-Pro.git
cd eOVPN-Pro/dist/arch
makepkg -si
```

---

### Option 4: AppImage (Portable / قابل حمل)
```bash
chmod +x eovpn-pro-1.5.0-x86_64.AppImage
./eovpn-pro-1.5.0-x86_64.AppImage
```
> ℹ️ The AppImage bundles the GTK4 user interface only. NetworkManager and its
> OpenVPN plugin must still be installed on the host system.
> این بسته فقط رابط کاربری GTK4 را باندل می‌کند؛ NetworkManager و افزونهٔ OpenVPN آن
> باید روی خود سیستم نصب باشند.

---

### Option 5: Flatpak (Universal Sandbox / جعبهٔ ایمن همگانی)
```bash
# From a published bundle / از روی باندل منتشرشده
flatpak install --user eovpn-pro.flatpak

# Or build locally / یا ساخت محلی
cd dist/flatpak
flatpak-builder --user --install --force-clean build-dir com.github.mahdi-arts.eovpn-pro.yml

flatpak run com.github.mahdi-arts.eovpn-pro
```

---

### Option 6: Global System Installation (Meson / Ninja)
```bash
# 1. Setup the meson build system / پیکربندی سیستم ساخت
meson setup build --prefix=/usr

# 2. Compile and install / کامپایل و نصب
sudo ninja install -C build
```

To uninstall / برای حذف نصب:
```bash
sudo ninja uninstall -C build
```

---

### Option 7: Local Python Debug Run (اجرای محلی برای توسعه)
```bash
# 1. Install dependencies / نصب وابستگی‌ها
pip install -r requirements.txt

# 2. Run the automated debug script / اجرای اسکریپت اشکال‌زدایی
python3 run_program_debug.py
```

*Detailed, distribution-by-distribution build instructions live in [PACKAGING.md](PACKAGING.md).*
*راهنمای کامل و توزیع‌به‌توزیع ساخت بسته‌ها در [PACKAGING.md](PACKAGING.md) آمده است.*

---

## 🧪 Testing & Quality Assurance (آزمون و تست نرم‌افزار)

The project ships **56 offline unit tests** that require no network, no D-Bus and
no display server, so they run identically on a laptop and inside CI.
این پروژه دارای **۵۶ تست واحد آفلاین** است که به شبکه، D-Bus یا سرور نمایش نیاز
ندارند و به همین دلیل روی سیستم شخصی و داخل CI یکسان اجرا می‌شوند.

```bash
# Unit tests / تست‌های واحد  (56 tests)
python3 -m unittest discover -s tests -v

# …or through Meson / یا از طریق Meson
meson test -C build --print-errorlogs

# Linting / بررسی کیفیت کد
pip install -r requirements-dev.txt
python3 -m ruff check .
python3 -m ruff format --check .

# Type checking / بررسی نوع‌ها
python3 -m mypy --ignore-missing-imports eovpn tests

# Project metadata consistency (versions / schema / resources)
# بررسی یکپارچگی متادیتا (نسخه‌ها / اسکیما / منابع)
python3 scripts/check_project_meta.py

# Security audit of dependencies / ممیزی امنیتی وابستگی‌ها
python3 -m pip_audit --requirement requirements.txt --strict

# Byte-compile all sources / کامپایل همه فایل‌ها
python3 -m compileall -q eovpn tests run_program_debug.py cffi_compile.py meson_post_install.py
```

### Continuous Integration (یکپارچه‌سازی مداوم)

| Workflow / وورک‌فلو | Trigger / محرک | What it does / وظیفه |
|---|---|---|
| [`ci.yml`](.github/workflows/ci.yml) | every push & pull request — هر push و pull request | Ruff lint + format check, mypy, 56 unit tests on Python 3.10/3.11/3.12, `pip-audit`, CodeQL, Meson build, and smoke builds of the `.deb`, `.rpm` and Arch packages |
| [`release.yml`](.github/workflows/release.yml) | version tags `v*.*.*` — تگ‌های نسخه | Verifies version parity across all packaging metadata, then builds `.deb`, `.rpm`, `.pkg.tar.zst`, AppImage and Flatpak, generates `SHA256SUMS`, and publishes the GitHub Release |

هر push و pull request توسط `ci.yml` بررسی می‌شود و ساخت و انتشار همهٔ قالب‌های بسته
با ایجاد تگ نسخه توسط `release.yml` به‌صورت خودکار انجام می‌گیرد.

---

## 📚 Documentation (مستندات)

| Document / مستند | Description / شرح |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | Version history — تاریخچه نسخه‌ها |
| [PACKAGING.md](PACKAGING.md) | Packaging guide (.deb / .rpm / Arch / AppImage / Flatpak) — راهنمای بسته‌بندی |
| [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) | Release runbook — راهنمای انتشار نسخه |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture overview — نمای کلی معماری |
| [docs/REVIEW_SENIOR_2026-08.md](docs/REVIEW_SENIOR_2026-08.md) | Senior engineering audit & action plan — ممیزی مهندسی ارشد و طرح اجرایی |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guide — راهنمای مشارکت |
| [SECURITY.md](SECURITY.md) | Security policy — خط مشی امنیتی |
| [docs/archive/](docs/archive/) | Superseded review reports — گزارش‌های بازبینی منسوخ |

---

## 💎 Project Information (مشخصات پروژه)

- **Application Display Name (نام نمایشی برنامه)**: eOVPN Pro
- **Repository Name (نام مخزن)**: eOVPN-Pro
- **Application ID (شناسه برنامه)**: `com.github.mahdi-arts.eovpn-pro`
- **Repository (آدرس مخزن پروژه)**: [github.com/Mahdi-Arts/eOVPN-Pro](https://github.com/Mahdi-Arts/eOVPN-Pro)
- **Issue Tracker (گزارش مشکلات)**: [github.com/Mahdi-Arts/eOVPN-Pro/issues](https://github.com/Mahdi-Arts/eOVPN-Pro/issues)
- **Current Version (نسخه)**: 1.5.0
- **Lead Developer & Publisher (توسعه‌دهنده اصلی)**: [Mahdi Bagheban](https://www.MahdiArts.ir)
- **Official Website (وب‌سایت رسمی)**: [MahdiArts](https://www.MahdiArts.ir)
- **Support Contact (ایمیل پشتیبانی)**: info@MahdiArts.ir / mehdi.bagheban@gmail.com

---

*یا علی مدد* 💚
