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

---

## 1. Debian / Ubuntu / Linux Mint (.deb)

### Prerequisites (پیش‌نیازها)
```bash
sudo apt update
sudo apt install -y build-essential debhelper dh-python meson ninja-build \
    pkg-config python3-all python3-cffi python3-gi libnm-dev libglib2.0-dev \
    libgtk-4-dev libadwaita-1-dev libsecret-1-dev libnotify-dev gettext \
    network-manager-openvpn openvpn
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

# Create source archive
tar --exclude-vcs -czf ~/rpmbuild/SOURCES/eovpn-pro-1.5.0.tar.gz .

# Build binary and source RPMs
rpmbuild -ba eovpn-pro.spec

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

# Install GNOME Sdk and Platform runtimes
flatpak install flathub org.gnome.Sdk//46 org.gnome.Platform//46
```

### Build Flatpak (ساخت فلت‌پک)
```bash
cd dist/flatpak

# Build application locally
flatpak-builder --user --install --force-clean build-dir com.github.mahdi-bagheban.eovpn-pro.yml

# Run the installed Flatpak
flatpak run com.github.mahdi-bagheban.eovpn-pro
```

### Export Single-File Bundle (.flatpak)
```bash
flatpak-builder --repo=repo --force-clean build-dir com.github.mahdi-bagheban.eovpn-pro.yml
flatpak build-bundle repo eovpn-pro.flatpak com.github.mahdi-bagheban.eovpn-pro
```

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

The repository includes a ready-to-use GitHub Actions workflow template (`dist/ci/ci-cd.yml`) that can be placed in `.github/workflows/ci-cd.yml` to automatically:
1. Run full offline test suite on pull requests and commits.
2. Build native `.deb` packages in Ubuntu runner environments.
3. Automatically attach the `.deb` installer to new GitHub Releases upon creating version tags (e.g. `git tag v1.5.0 && git push origin v1.5.0`).

---

*یا علی مدد 💚*
