# 📦 eOVPN-Pro Packaging & Deployment Guide
# راهنمای جامع بسته‌بندی و استقرار eOVPN-Pro

This guide provides step-by-step instructions for building and packaging **eOVPN-Pro**
across every supported Linux packaging format: `.deb`, `.rpm`, `.pkg.tar.zst` (Arch),
AppImage and Flatpak.

این مستند راهنمای گام‌به‌گام کامپایل و ساخت بسته‌های نصبی **eOVPN-Pro** برای همهٔ قالب‌های
پشتیبانی‌شده است: `.deb`، `.rpm`، `.pkg.tar.zst` (آرچ)، AppImage و Flatpak.

---

## 📑 Table of Contents (فهرست مطالب)
1. [Debian / Ubuntu / Linux Mint (.deb)](#1-debian--ubuntu--linux-mint-deb)
2. [Fedora / RHEL / openSUSE (.rpm)](#2-fedora--rhel--opensuse-rpm)
3. [Arch Linux / Manjaro (.pkg.tar.zst)](#3-arch-linux--manjaro-pkgtarzst)
4. [AppImage (Portable)](#4-appimage-portable)
5. [Flatpak (Universal Sandbox)](#5-flatpak-universal-sandbox)
6. [Automated CI/CD Deployment](#6-automated-cicd-deployment)
7. [Format Support Matrix](#7-format-support-matrix)

> **Note:** The OpenVPN 3 (DCO) backend is optional (`-Dopenvpn3=false` by default).
> Building with `-Dopenvpn3=true` additionally requires the Python `openvpn3` bindings
> installed in the *build* environment (`pip install openvpn3`). All distribution
> packages below are built with the OpenVPN 3 backend **disabled**, because
> NetworkManager is the default backend and is available everywhere.
>
> **نکته:** بک‌اند OpenVPN 3 (DCO) اختیاری است (پیش‌فرض `-Dopenvpn3=false`). ساخت با
> `-Dopenvpn3=true` نیازمند نصب بایندینگ پایتون `openvpn3` در محیط ساخت است. همهٔ
> بسته‌های توزیع‌ها با بک‌اند OpenVPN 3 **غیرفعال** ساخته می‌شوند، چون NetworkManager
> بک‌اند پیش‌فرض است و روی همهٔ توزیع‌ها در دسترس قرار دارد.

---

## 1. Debian / Ubuntu / Linux Mint (.deb)

### Prerequisites (پیش‌نیازها)
```bash
sudo apt update
sudo apt install -y build-essential debhelper dh-python meson ninja-build \
    pkg-config python3-all python3-dev python3-cffi python3-gi libnm-dev \
    libglib2.0-dev libgtk-4-dev libadwaita-1-dev libsecret-1-dev libnotify-dev \
    gettext desktop-file-utils network-manager-openvpn openvpn lintian
```

### Build .deb Package (ساخت بسته دبیان)
From the repository root / از ریشهٔ مخزن:
```bash
# Option A — the helper script (recommended) / اسکریپت کمکی (پیشنهادی)
bash scripts/build-deb.sh

# Option B — invoke dpkg directly / فراخوانی مستقیم dpkg
dpkg-buildpackage -us -uc -b

# The resulting package lands in the parent directory:
# بستهٔ خروجی در پوشهٔ والد ساخته می‌شود:
#   ../eovpn-pro_1.5.0-1_amd64.deb
```

### Quality Check (بررسی کیفیت بسته)
```bash
lintian ../eovpn-pro_1.5.0-1_amd64.deb
```

### Installation & Removal (نصب و حذف)
```bash
# Install (resolves dependencies automatically) / نصب همراه با حل خودکار وابستگی‌ها
sudo apt install ../eovpn-pro_1.5.0-1_amd64.deb

# Remove, keeping configuration / حذف با نگهداری تنظیمات
sudo apt remove eovpn-pro

# Purge everything / حذف کامل به همراه تنظیمات
sudo apt purge eovpn-pro
```

---

## 2. Fedora / RHEL / openSUSE (.rpm)

### Prerequisites (پیش‌نیازها)
```bash
sudo dnf install -y rpm-build rpmdevtools meson ninja-build gcc \
    pkgconf-pkg-config NetworkManager-libnm-devel glib2-devel gtk4-devel \
    libadwaita-devel libsecret-devel libnotify-devel python3-devel \
    python3-cffi gettext desktop-file-utils libappstream-glib
```

### Build .rpm Package (ساخت بسته آرپی‌ام)
```bash
# 1. Set up the RPM build tree / آماده‌سازی درخت ساخت RPM
rpmdev-setuptree

# 2. Create the source archive — the top-level directory MUST match
#    %{name}-%{version}, because the spec uses %autosetup.
#    ساخت آرشیو منبع؛ نام پوشهٔ ریشه باید دقیقاً %{name}-%{version} باشد
#    چون اسپک از %autosetup استفاده می‌کند.
git archive --prefix=eovpn-pro-1.5.0/ \
    -o ~/rpmbuild/SOURCES/eovpn-pro-1.5.0.tar.gz HEAD

# 3. Build from the canonical spec (single source of truth)
#    ساخت از روی اسپک مرجع پروژه
rpmbuild -bb dist/rpm/eovpn-pro.spec

# Output / خروجی: ~/rpmbuild/RPMS/x86_64/eovpn-pro-1.5.0-1.*.rpm
```

> The spec's `%check` stage runs `desktop-file-validate` and `appstreamcli validate`
> against the staged tree, so a malformed desktop entry or AppStream file fails the build.
> مرحلهٔ `%check` در اسپک، فایل desktop و AppStream را اعتبارسنجی می‌کند و خطای آن‌ها
> باعث شکست ساخت می‌شود.

### Installation (نصب بسته)
```bash
sudo dnf install ~/rpmbuild/RPMS/x86_64/eovpn-pro-1.5.0-1.*.rpm
```

---

## 3. Arch Linux / Manjaro (.pkg.tar.zst)

The canonical recipe lives at **`dist/arch/PKGBUILD`** and is validated on every push
by CI. It is *dual-mode*: run from inside a repository checkout it builds the working
tree directly; run standalone (as the AUR does) it downloads the tagged release tarball.

دستور ساخت مرجع در **`dist/arch/PKGBUILD`** قرار دارد و در هر push توسط CI بررسی می‌شود.
این فایل دو حالته است: اگر از داخل یک کپی از مخزن اجرا شود همان درخت کاری را می‌سازد و
اگر مستقل اجرا شود (روش AUR) آرشیو نسخهٔ تگ‌خورده را دانلود می‌کند.

### Prerequisites (پیش‌نیازها)
```bash
sudo pacman -S --needed base-devel meson ninja pkgconf gcc gettext \
    desktop-file-utils appstream-glib python python-gobject python-cffi \
    gtk4 libadwaita libsecret libnotify networkmanager networkmanager-openvpn openvpn
```

### Build & Install (ساخت و نصب)
```bash
git clone https://github.com/Mahdi-Arts/eOVPN-Pro.git
cd eOVPN-Pro/dist/arch

# Build and install in one step / ساخت و نصب در یک مرحله
makepkg -si

# Or build only, without installing / یا فقط ساخت بدون نصب
makepkg -sf --skipinteg
sudo pacman -U eovpn-pro-1.5.0-1-x86_64.pkg.tar.zst
```

> `makepkg` runs the project's 56 offline unit tests in its `check()` stage.
> Pass `--nocheck` to skip them inside minimal containers.
> دستور `makepkg` در مرحلهٔ `check()` هر ۵۶ تست واحد آفلاین را اجرا می‌کند؛ برای رد کردن
> آن‌ها در کانتینرهای حداقلی از `--nocheck` استفاده کنید.

### Enabling the OpenVPN 3 backend (فعال‌سازی بک‌اند OpenVPN 3)
`openvpn3` is not in the official Arch repositories, so it is declared as an
`optdepends`. After installing it from the AUR, rebuild with:
بستهٔ `openvpn3` در مخازن رسمی آرچ نیست و به‌صورت `optdepends` اعلام شده است. پس از نصب
آن از AUR، با تغییر زیر دوباره بسازید:
```bash
# in dist/arch/PKGBUILD → build() → -Dopenvpn3=true
```

### AUR metadata (متادیتای AUR)
`dist/arch/.SRCINFO` is the machine-readable metadata the AUR requires. Regenerate it
after **any** change to the `PKGBUILD`:
فایل `dist/arch/.SRCINFO` متادیتای موردنیاز AUR است و پس از **هر** تغییر در `PKGBUILD`
باید بازتولید شود:
```bash
cd dist/arch && makepkg --printsrcinfo > .SRCINFO
```

---

## 4. AppImage (Portable)

A single self-contained executable that runs on any reasonably modern x86-64
distribution without installation.

یک فایل اجرایی مستقل که بدون نصب، روی هر توزیع نسبتاً جدید x86-64 اجرا می‌شود.

### Prerequisites (پیش‌نیازها)
```bash
sudo apt install -y meson ninja-build pkg-config libfuse2 wget file \
    python3-dev python3-cffi python3-gi libnm-dev libglib2.0-dev libgtk-4-dev \
    libadwaita-1-dev libsecret-1-dev libnotify-dev gettext desktop-file-utils

# linuxdeploy + the GTK plugin / ابزار linuxdeploy و افزونهٔ GTK آن
mkdir -p ~/.local/bin && cd ~/.local/bin
wget -O linuxdeploy \
  https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
wget -O linuxdeploy-plugin-gtk.sh \
  https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/master/linuxdeploy-plugin-gtk.sh
chmod +x linuxdeploy linuxdeploy-plugin-gtk.sh
export PATH="$HOME/.local/bin:$PATH"
```

### Build (ساخت)
```bash
VERSION=1.5.0 bash dist/appimage/build-appimage.sh
# Output / خروجی: eovpn-pro-1.5.0-x86_64.AppImage
```

If `linuxdeploy` is not on `PATH`, the script still prepares a complete `AppDir/`
that you can inspect or package with another tool.
اگر `linuxdeploy` در مسیر `PATH` نباشد، اسکریپت همچنان یک `AppDir/` کامل می‌سازد که
می‌توانید آن را بررسی یا با ابزار دیگری بسته‌بندی کنید.

### Run (اجرا)
```bash
chmod +x eovpn-pro-1.5.0-x86_64.AppImage
./eovpn-pro-1.5.0-x86_64.AppImage
```

> ⚠️ **Host requirement / پیش‌نیاز میزبان:** the AppImage bundles the GTK4 UI stack
> only. eOVPN-Pro drives the **system** NetworkManager / OpenVPN 3 D-Bus services, so
> `network-manager-openvpn`, `openvpn` and a Secret Service provider (GNOME Keyring or
> KWallet) must be present on the host.
> این بسته فقط پشتهٔ رابط کاربری GTK4 را باندل می‌کند. برنامه سرویس‌های **سیستمی**
> NetworkManager / OpenVPN 3 را از طریق D-Bus فرا می‌خواند، پس نصب بودن
> `network-manager-openvpn`، `openvpn` و یک سرویس Secret Service روی میزبان الزامی است.

---

## 5. Flatpak (Universal Sandbox)

Flatpak provides an isolated, sandboxed container ensuring compatibility across all
modern Linux desktops.

بسته فلت‌پک به عنوان یک فرمت ایزوله و مستقل، سازگاری برنامه را در تمام توزیع‌های لینوکس
تضمین می‌کند.

### Prerequisites (پیش‌نیازها)
```bash
# Install flatpak and flatpak-builder / نصب flatpak و flatpak-builder
sudo apt install flatpak flatpak-builder     # Ubuntu/Debian
# sudo dnf install flatpak flatpak-builder   # Fedora

# Install the GNOME runtimes matching the manifest's runtime-version
# نصب رانتایم‌های GNOME هماهنگ با runtime-version در مانیفست
flatpak remote-add --if-not-exists --user \
    flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.gnome.Sdk//50 org.gnome.Platform//50
```

### Build Flatpak (ساخت فلت‌پک)
```bash
# Option A — the helper script / اسکریپت کمکی
bash scripts/build-flatpak.sh

# Option B — manual / روش دستی
cd dist/flatpak
flatpak-builder --user --install --force-clean build-dir \
    com.github.mahdi-arts.eovpn-pro.yml

flatpak run com.github.mahdi-arts.eovpn-pro
```

### Export a Single-File Bundle (.flatpak)
```bash
cd dist/flatpak
flatpak-builder --repo=repo --force-clean build-dir \
    com.github.mahdi-arts.eovpn-pro.yml
flatpak build-bundle repo eovpn-pro.flatpak com.github.mahdi-arts.eovpn-pro

# Install the bundle elsewhere / نصب باندل روی سیستم دیگر
flatpak install --user eovpn-pro.flatpak
```

> ⏱️ The manifest builds NetworkManager, libnma, eudev, protobuf and OpenVPN 3 from
> source. A cold build takes **well over an hour**; keep the `.flatpak-builder/` cache
> between runs.
> مانیفست، NetworkManager و libnma و eudev و protobuf و OpenVPN 3 را از منبع می‌سازد.
> ساخت اول **بیش از یک ساعت** طول می‌کشد؛ پوشهٔ کش `.flatpak-builder/` را حفظ کنید.

---

## 6. Automated CI/CD Deployment

The repository ships two GitHub Actions workflows.
مخزن دارای دو وورک‌فلوی GitHub Actions است.

### `.github/workflows/ci.yml` — Continuous Integration
Runs on every push to `master`/`arena/**`, on every pull request, and on demand.
روی هر push به `master` و `arena/**`، هر pull request و به‌صورت دستی اجرا می‌شود.

| Job | Purpose / وظیفه |
|---|---|
| `quality` | Ruff lint + format check, mypy, 56 unit tests on Python 3.10 / 3.11 / 3.12, metadata consistency, byte-compile |
| `security` | `pip-audit --strict` against `requirements.txt` + CodeQL static analysis |
| `build-meson` | Full Meson build, `meson test`, staged install, `desktop-file-validate`, `appstreamcli validate`, `msgfmt --check` on every `po/*.po` |
| `build-deb` | `dpkg-buildpackage` + `lintian`, uploads the `.deb` as an artifact |
| `build-rpm` | Builds the RPM inside a `fedora:41` container |
| `build-arch` | Builds the Arch package inside an `archlinux:base-devel` container |
| `ci-summary` | Aggregate gate — fails if any required job failed |

### `.github/workflows/release.yml` — Release Automation
Triggered by a semantic version tag.
با ایجاد تگ نسخهٔ معنایی فعال می‌شود.

1. **`prepare`** — verifies that `meson.build`, `debian/changelog`, the RPM spec, the
   AppStream metainfo and the README all declare the same version as the tag, then runs
   the unit tests. A mismatch aborts the release.
   بررسی می‌کند که نسخهٔ اعلام‌شده در همهٔ فایل‌های متادیتا با تگ یکسان باشد و تست‌ها را
   اجرا می‌کند؛ هر ناهماهنگی، انتشار را متوقف می‌کند.
2. **`deb` / `rpm` / `arch` / `appimage` / `flatpak`** — build all five formats in parallel.
   ساخت موازی هر پنج قالب بسته.
3. **`publish`** — collects the artifacts, generates `SHA256SUMS`, extracts the matching
   section from `CHANGELOG.md` as release notes, and publishes the GitHub Release.
   جمع‌آوری خروجی‌ها، تولید `SHA256SUMS`، استخراج بخش متناظر از `CHANGELOG.md` به‌عنوان
   یادداشت انتشار و انتشار نسخه در GitHub.

To publish a release / برای انتشار یک نسخه:
```bash
# 1. Bump the version everywhere, then verify / تغییر نسخه در همه‌جا و سپس بررسی
python3 scripts/check_project_meta.py

# 2. Tag and push / ایجاد تگ و ارسال آن
git tag -a v1.5.0 -m "eOVPN-Pro 1.5.0"
git push origin v1.5.0
```

Dependabot (`.github/dependabot.yml`) keeps GitHub Actions and Python dependencies
updated weekly.
سرویس Dependabot به‌صورت هفتگی، اکشن‌های GitHub و وابستگی‌های پایتون را به‌روز نگه می‌دارد.

See [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) for the full release runbook.
راهنمای کامل انتشار در [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) موجود است.

---

## 7. Format Support Matrix

| Format / قالب | Recipe / دستور ساخت | Built in CI | Published on release | Maturity / بلوغ |
|---|---|:--:|:--:|---|
| `.deb` | `debian/` + `scripts/build-deb.sh` | ✅ | ✅ | 🟢 Production / آمادهٔ تولید |
| `.rpm` | `dist/rpm/eovpn-pro.spec` | ✅ | ✅ | 🟢 Production / آمادهٔ تولید |
| `.pkg.tar.zst` | `dist/arch/PKGBUILD` | ✅ | ✅ | 🟢 Production / آمادهٔ تولید |
| AppImage | `dist/appimage/build-appimage.sh` | ➖ | ✅ | 🟡 Beta — needs host NM / نیازمند NM میزبان |
| Flatpak | `dist/flatpak/*.yml` | ➖ | ✅ (best-effort) | 🟡 Beta — long cold build / ساخت اول طولانی |

Legend / راهنما: ✅ enforced · ➖ not run (build cost) · 🟢 stable · 🟡 usable with caveats

---

*یا علی مدد 💚*
