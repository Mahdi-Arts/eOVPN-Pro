# 📦 eOVPN-Pro Packaging & Deployment Guide
# راهنمای جامع بسته‌بندی و استقرار eOVPN-Pro

This guide provides step-by-step instructions for building and packaging **eOVPN-Pro** across major Linux distributions (.deb, .rpm, Flatpak, and Arch Linux).

این مستند راهنمای گام‌به‌گام نحوه کامپایل و ایجاد بسته‌های نصبی برای توزیع‌های مختلف لینوکس (.deb, .rpm, Flatpak و Arch Linux) است.

---

## 📑 Table of Contents (فهرست مطالب)
1. [Debian / Ubuntu / Linux Mint (.deb)](#1-debian--ubuntu--linux-mint-deb)
2. [Fedora / RHEL / openSUSE (.rpm)](#2-fedora--rhel--opensuse-rpm)
3. [Flatpak (Universal Sandbox)](#3-flatpak-universal-sandbox)
4. [Arch Linux / Manjaro (PKGBUILD)](#4-arch-linux--manjaro-pkgbuild)
5. [Automated CI/CD Deployment](#5-automated-cicd-deployment)
6. [AppImage status](#6-appimage-status)

> **Note:** The OpenVPN 3 (DCO) backend is optional (`-Dopenvpn3=false` by default).
> Building with `-Dopenvpn3=true` additionally requires the Python `openvpn3` bindings
> installed in the *build* environment (`pip install openvpn3`).
> **نکته:** بک‌اند OpenVPN 3 (DCO) اختیاری است (پیش‌فرض `-Dopenvpn3=false`). ساخت با
> `-Dopenvpn3=true` نیازمند نصب بایندینگ پایتون `openvpn3` در محیط ساخت است.

---

## 1. Debian / Ubuntu / Linux Mint (.deb)

### Prerequisites (پیش‌نیازها)
```bash
sudo apt update
sudo apt install -y build-essential debhelper dh-python meson ninja-build \
    pkg-config python3-all python3-cffi python3-gi libnm-dev libglib2.0-dev \
    libgtk-4-dev libadwaita-1-dev libsecret-1-dev libnotify-dev gettext \
    desktop-file-utils network-manager-openvpn openvpn
```

### Build .deb Package (ساخت بسته دبیان)
From the repository root:
```bash
# Build binary package
dpkg-buildpackage -us -uc -b

# The resulting .deb package will be generated in the parent directory:
# ../eovpn-pro_1.5.0-1_amd64.deb
```

### Installation (نصب بسته)
```bash
sudo dpkg -i ../eovpn-pro_1.5.0-1_amd64.deb
sudo apt install -f  # Resolve any missing dependencies if needed
```

### Uninstall (حذف نصب)
```bash
sudo dpkg -r eovpn-pro
```

---

## 2. Fedora / RHEL / openSUSE (.rpm)

### Prerequisites (پیش‌نیازها)
```bash
sudo dnf install -y rpm-build rpmdevtools meson ninja-build gcc \
    pkgconfig NetworkManager-libnm-devel glib2-devel gtk4-devel \
    libadwaita-devel libsecret-devel libnotify-devel python3-devel \
    python3-cffi gettext desktop-file-utils libappstream-glib
```

### Build .rpm Package (ساخت بسته آرپی‌ام)
```bash
# Setup RPM build tree
rpmdev-setuptree

# Create source archive (top-level dir must match %{name}-%{version})
# ساخت آرشیو سورس (پوشه ریشه باید با %{name}-%{version} یکسان باشد)
git archive --prefix=eovpn-pro-1.5.0/ -o ~/rpmbuild/SOURCES/eovpn-pro-1.5.0.tar.gz HEAD

# Copy the canonical spec (single source of truth) and build
cp dist/rpm/eovpn-pro.spec ~/rpmbuild/SPECS/
rpmbuild -ba ~/rpmbuild/SPECS/eovpn-pro.spec

# The resulting package will be in ~/rpmbuild/RPMS/x86_64/
```

### Installation (نصب بسته)
```bash
sudo dnf install ~/rpmbuild/RPMS/x86_64/eovpn-pro-1.5.0-1.*.rpm
```

---

## 3. Flatpak (Universal Sandbox)

Flatpak provides an isolated, sandboxed container ensuring compatibility across all modern Linux desktops.

بسته فلت‌پک به عنوان یک فرمت ایزوله و مستقل، سازگاری برنامه را در تمام توزیع‌های لینوکس تضمین می‌کند.

### Prerequisites (پیش‌نیازها)
```bash
# Install flatpak and flatpak-builder
sudo apt install flatpak flatpak-builder # Ubuntu/Debian
# sudo dnf install flatpak flatpak-builder # Fedora

# Install GNOME Sdk and Platform runtimes (match the manifest's runtime-version)
# نصب رانتایم‌های GNOME (هماهنگ با runtime-version در مانیفست)
flatpak install flathub org.gnome.Sdk//50 org.gnome.Platform//50
```

### Build Flatpak (ساخت فلت‌پک)
```bash
cd dist/flatpak

# Build application locally
flatpak-builder --user --install --force-clean build-dir com.github.mahdi-arts.eovpn-pro.yml

# Run the installed Flatpak
flatpak run com.github.mahdi-arts.eovpn-pro
```

### Export Single-File Bundle (.flatpak)
```bash
flatpak-builder --repo=repo --force-clean build-dir com.github.mahdi-arts.eovpn-pro.yml
flatpak build-bundle repo eovpn-pro.flatpak com.github.mahdi-arts.eovpn-pro
```

> The manifest builds NetworkManager, libnma and OpenVPN 3 from source; the first build
> takes a long time and requires the `flatpak-builder` caches to be warm.
> مانیفست NetworkManager و OpenVPN 3 را از سورس می‌سازد؛ ساخت اول زمان‌بر است.

---

## 4. Arch Linux / Manjaro (PKGBUILD)

For Arch Linux users, an example `PKGBUILD` structure:

```bash
# Maintainer: Mahdi Bagheban <info@MahdiArts.ir>
pkgname=eovpn-pro
pkgver=1.5.0
pkgrel=1
pkgdesc="Advanced OpenVPN GUI Client with Speed Testing (Pro Edition)"
arch=('x86_64')
url="https://github.com/Mahdi-Arts/eOVPN-Pro"
license=('GPL3')
depends=('gtk4' 'libadwaita' 'libnm' 'libsecret' 'libnotify' 'python' 'python-gobject' 'python-cffi' 'networkmanager-openvpn' 'openvpn')
makedepends=('meson' 'ninja' 'pkgconf')
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    arch-meson "$pkgname-$pkgver" build -Dopenvpn3=false
    ninja -C build
}

package() {
    DESTDIR="$pkgdir" ninja -C build install
}
```

---

## 5. Automated CI/CD Deployment

The repository ships one active GitHub Actions workflow — `.github/workflows/ci-cd.yml` —
with the following jobs (all run automatically on every push/PR):

1. **test**: unit tests, flake8/ruff/mypy linting, `pip-audit` CVE scanning, metadata
   consistency checks and byte-compilation on every commit/PR.
2. **build-deb**: builds the native `.deb` package on Ubuntu runners.
3. **build-rpm**: builds the native `.rpm` package inside a Fedora container.
4. **build-flatpak**: builds the Flatpak bundle on version tags (and manual dispatch).
5. **release**: attaches both `.deb` and `.flatpak` artifacts to a new GitHub Release
   when a version tag is pushed (e.g. `git tag v1.5.0 && git push origin v1.5.0`).

Dependabot (`.github/dependabot.yml`) keeps GitHub Actions and Python dependencies
updated weekly.

مخزن یک وورک‌فلو فعال گیت‌هاب اکشن دارد — `.github/workflows/ci-cd.yml` — با وظایف:
تست/لینت/ممیزی CVE، ساخت .deb، ساخت .rpm، ساخت Flatpak و انتشار خودکار بسته‌ها روی تگ.

See `docs/RELEASE_CHECKLIST.md` for the full release runbook.
راهنمای کامل انتشار در `docs/RELEASE_CHECKLIST.md` موجود است.

---

## 6. AppImage status

**Experimental scaffold — not production-ready.** See `dist/appimage/` for the
`linuxdeploy` recipe and build script. eOVPN-Pro talks to the **system**
NetworkManager / OpenVPN 3 D-Bus services, so even a portable AppImage would still
require those host services (and the OpenVPN NM plugin) to be installed. A GTK4 +
PyGObject + CFFI native-library bundle is a separate engineering task, not a
packaging-file tweak; it is not wired into CI yet.

**زیرساخت آزمایشی — آماده تولید نیست.** دستور `linuxdeploy` و اسکریپت ساخت در
`dist/appimage/` قرار دارد. برنامه با سرویس‌های سیستمی NetworkManager / OpenVPN 3
صحبت می‌کند؛ بنابراین حتی یک AppImage قابل‌حمل هم به نصب بودن آن سرویس‌ها روی
میزبان نیاز دارد و هنوز به CI متصل نشده است.

---

*یا علی مدد 💚*
