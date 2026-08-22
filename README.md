# ⚡ eOVPN-Pro

<div align="center">
    <img src="static/window_connected_with_flag.png" alt="eOVPN-Pro" width="600">
</div>

<div align="center">

[![Repository](https://img.shields.io/badge/GitHub-Mahdi--Arts%2FeOVPN--Pro-181717?logo=github)](https://github.com/Mahdi-Arts/eOVPN-Pro)
[![Version](https://img.shields.io/badge/version-1.5.0-3E8914)](https://github.com/Mahdi-Arts/eOVPN-Pro/releases)
[![Packaging](https://img.shields.io/badge/Package-.deb%20%7C%20.rpm%20%7C%20Flatpak-blue)](PACKAGING.md)
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

- 🔄 **Dynamic Latency Sorting & Auto-Select (مرتب‌سازی داینامیک و انتخاب هوشمند)**:
  - Instantly sorts your VPN configuration list from lowest to highest latency, moving failed servers to the bottom automatically, and auto-selects the fastest server with one click.
  - مرتب‌سازی آنی لیست کانفیگ‌ها از سریع‌ترین (کمترین پینگ) به سنگین‌ترین سرورها به صورت کاملاً خودکار و انتخاب سریع‌ترین سرور فعال در کل لیست تنها با یک کلیک.

- 📊 **Real-time Bandwidth Monitor (نمایشگر زنده پهنای باند و ترافیک)**:
  - Monitors and displays live download speed, upload speed, and total traffic usage from `/proc/net/dev` once connected.
  - مانیتورینگ زنده و نمایش گرافیکی نرخ دانلود، آپلود و میزان کل مصرف ترافیک اینترنت کارت شبکه VPN به صورت زنده و ثانیه‌ای.

- 🛡️ **Security Hardened Architecture (معماری امن و محافظت‌شده)**:
  - Zero plaintext password leakage into disk/dconf (GNOME Keyring with volatile RAM fallback), secure temporary file generation (`0o600` permissions), Zip-Slip path traversal protection, and encrypted HTTPS IP lookups.
  - عدم ذخیره متن خام رمز عبور روی دیسک، ایجاد ایمن فایل‌های موقت با پرمیشن `0600`، جلوگیری از آسیب‌پذیری‌های فایل فشرده (Zip-Slip) و استعلام امن موقعیت مکانی از طریق پروتکل HTTPS.

- 🔌 **Auto-Reconnect (اتصال مجدد خودکار)**:
  - Detects unexpected connection drops and automatically schedules an immediate reconnect attempt within 3 seconds.
  - شناسایی هوشمند قطعی‌های ناگهانی فیلترشکن و اقدام خودکار جهت اتصال مجدد در ۳ ثانیه.

- 📁 **Local Folder & ZIP Import (وارد کردن دسته‌جمعی و پوشه‌ای کانفیگ‌ها)**:
  - Supports importing VPN configurations directly from a local folder path in addition to ZIP archives.
  - امکان وارد کردن مستقیم فایل‌های کانفیگ از یک پوشه در سیستم یا فایل‌های فشرده ZIP.

---

## 🛠️ Installation & Execution (نصب و اجرا)

### Option 1: Debian / Ubuntu Package (.deb) — *Recommended*
Download the latest `.deb` release package from [GitHub Releases](https://github.com/Mahdi-Arts/eOVPN-Pro/releases) and install:
```bash
sudo dpkg -i eovpn-pro_1.5.0-1_amd64.deb
sudo apt install -f
```

---

### Option 2: Flatpak (Universal Sandbox)
```bash
cd dist/flatpak
flatpak-builder --user --install --force-clean build-dir com.github.mahdi-bagheban.eovpn-pro.yml
flatpak run com.github.mahdi-bagheban.eovpn-pro
```

---

### Option 3: Global System Installation (Meson / Ninja)
```bash
# 1. Setup the meson build system
meson setup build -Dprefix=/usr

# 2. Compile and install
sudo ninja install -C build
```

To uninstall:
```bash
sudo ninja uninstall -C build
```

---

### Option 4: Local Python Debug Run
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the automated debug script
python3 run_program_debug.py
```

*For building `.rpm` (Fedora/RHEL) and Arch Linux packages, refer to [PACKAGING.md](PACKAGING.md).*

---

## 🧪 Testing & Quality Assurance (آزمون و تست نرم‌افزار)

Run the full offline test suite:
```bash
python3 -m unittest discover -s tests -v
```

---

## 💎 Project Information (مشخصات پروژه)

- **Application Display Name (نام نمایشی برنامه)**: eOVPN Pro
- **Repository Name (نام مخزن)**: eOVPN-Pro
- **Application ID (شناسه برنامه)**: `com.github.mahdi-bagheban.eovpn-pro`
- **Repository (آدرس مخزن پروژه)**: [github.com/Mahdi-Arts/eOVPN-Pro](https://github.com/Mahdi-Arts/eOVPN-Pro)
- **Issue Tracker (گزارش مشکلات)**: [github.com/Mahdi-Arts/eOVPN-Pro/issues](https://github.com/Mahdi-Arts/eOVPN-Pro/issues)
- **Current Version (نسخه)**: 1.5.0
- **Lead Developer & Publisher (توسعه‌دهنده اصلی)**: [Mahdi Bagheban](https://www.MahdiArts.ir)
- **Official Website (وب‌سایت رسمی)**: [MahdiArts](https://www.MahdiArts.ir)
- **Support Contact (ایمیل پشتیبانی)**: info@MahdiArts.ir / mehdi.bagheban@gmail.com

---

*یا علی مدد* 💚
