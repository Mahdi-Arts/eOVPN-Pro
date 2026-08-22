#!/usr/bin/env bash
# Build a Debian package locally.
# ساخت بسته Debian به‌صورت محلی.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "==> Installing Debian build dependencies (requires sudo)"
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  build-essential debhelper dh-python meson ninja-build \
  pkg-config python3-all python3-cffi libnm-dev libglib2.0-dev \
  libgtk-4-dev libadwaita-1-dev libsecret-1-dev libnotify-dev \
  gettext desktop-file-utils

echo "==> Building .deb"
dpkg-buildpackage -us -uc -b

echo "==> Result"
ls -lh ../eovpn-pro_*.deb
