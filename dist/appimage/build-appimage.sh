#!/usr/bin/env bash
# ============================================================================
# eOVPN-Pro AppImage build script (experimental)
# اسکریپت ساخت AppImage برای eOVPN-Pro (آزمایشی)
#
# This script installs the Meson-built application into AppDir and bundles the
# generated resources/schemas/native CFFI libraries. eOVPN-Pro still talks to the
# host NetworkManager/OpenVPN 3 D-Bus services, so an AppImage is a portable UI
# bundle, not a self-contained VPN stack.
#
# این اسکریپت خروجی Meson را داخل AppDir نصب می‌کند و gresource، schemaها و
# کتابخانه‌های CFFI را باندل می‌کند. AppImage همچنان به سرویس‌های D-Bus میزبان
# نیاز دارد.
# ============================================================================
set -euo pipefail

APP_NAME="eOVPN-Pro"
APP_ID="com.github.mahdi-arts.eovpn-pro"
VERSION="${VERSION:-1.5.0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${BUILD_DIR:-${ROOT_DIR}/build-appimage}"
APPDIR="${APPDIR:-$(pwd)/AppDir}"
ARCH="${ARCH:-x86_64}"
OUTPUT="eovpn-pro-${VERSION}-${ARCH}.AppImage"

echo "==> Building eOVPN-Pro into ${APPDIR}"
rm -rf "${BUILD_DIR}" "${APPDIR}"
meson setup "${BUILD_DIR}" "${ROOT_DIR}" \
  --prefix=/usr \
  --buildtype=release \
  -Dopenvpn3=false
DESTDIR="${APPDIR}" meson install -C "${BUILD_DIR}"

# AppImages expect the desktop file and icon in standard AppDir locations.
# مسیرهای استاندارد AppDir برای desktop و آیکون.
mkdir -p "${APPDIR}/usr/share/applications" \
         "${APPDIR}/usr/share/icons/hicolor/scalable/apps"
cp "${ROOT_DIR}/data/${APP_ID}.desktop" "${APPDIR}/usr/share/applications/"
cp "${ROOT_DIR}/data/icons/${APP_ID}.svg" \
   "${APPDIR}/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg"

# Compile schemas inside the bundle. The wrapper exports GSETTINGS_SCHEMA_DIR.
# کامپایل schemaها درون باندل.
glib-compile-schemas "${APPDIR}/usr/share/glib-2.0/schemas"

# linuxdeploy is the recommended external packager. CI can download it before
# invoking this script. If it is absent, AppDir remains available for testing.
if command -v linuxdeploy >/dev/null 2>&1; then
  linuxdeploy --appdir "${APPDIR}" \
    --executable "${APPDIR}/usr/bin/eovpn" \
    --desktop-file "${APPDIR}/usr/share/applications/${APP_ID}.desktop" \
    --icon-file "${APPDIR}/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg" \
    --plugin gtk \
    --output appimage
  echo "==> Done: ${OUTPUT}"
else
  echo "==> linuxdeploy not found; AppDir prepared at ${APPDIR}"
  echo "    Install linuxdeploy and the GTK plugin to produce ${OUTPUT}."
fi
