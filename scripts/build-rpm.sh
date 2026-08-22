#!/usr/bin/env bash
# Build an RPM package locally (Fedora / RHEL / openSUSE).
# ساخت بسته RPM به‌صورت محلی (فدورا / RHEL / openSUSE).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

VERSION="$(grep -oP "version:\s*'\K[0-9.]+" meson.build | head -1)"
SPEC="dist/rpm/eovpn-pro.spec"
TARBALL="eovpn-pro-${VERSION}.tar.gz"

echo "==> Installing RPM build dependencies (requires sudo)"
sudo dnf install -y \
  rpm-build meson ninja-build gcc pkgconf-pkg-config \
  python3-devel python3-cffi NetworkManager-libnm-devel \
  glib2-devel gtk4-devel libadwaita-devel libsecret-devel \
  libnotify-devel gettext desktop-file-utils appstream

echo "==> Preparing source tarball (${TARBALL})"
mkdir -p "$HOME/rpmbuild/SOURCES"
git archive --prefix="eovpn-pro-${VERSION}/" -o \
  "$HOME/rpmbuild/SOURCES/${TARBALL}" HEAD

echo "==> Building .rpm"
rpmbuild -ba "${SPEC}"

echo "==> Result"
ls -lh "$HOME"/rpmbuild/RPMS/*/*.rpm
