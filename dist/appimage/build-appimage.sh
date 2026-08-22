#!/usr/bin/env bash
# ============================================================================
# eOVPN-Pro AppImage build script
# اسکریپت ساخت AppImage برای eOVPN-Pro
#
# Installs the Meson-built application into AppDir, bundles resources/schemas/
# native CFFI libraries, and writes a real AppRun wrapper that exports
# GSETTINGS_SCHEMA_DIR / PYTHONPATH / XDG_DATA_DIRS so the bundle is
# self-contained. eOVPN-Pro still talks to the host NetworkManager / OpenVPN 3
# D-Bus services, so an AppImage is a portable UI bundle, not a self-contained
# VPN stack.
#
# خروجی Meson را داخل AppDir نصب می‌کند، منابع/اسکیماها/کتابخانه‌های CFFI را
# باندل می‌کند و یک AppRun واقعی می‌سازد که مسیرهای schema و پایتون را صادر
# می‌کند تا باندل خودکفا باشد. برنامه همچنان به سرویس‌های D-Bus میزبان نیاز
# دارد؛ بنابراین AppImage یک باندل UI قابل حمل است، نه پشته کامل VPN.
#
# Env: VERSION, ARCH, BUILD_DIR, APPDIR, LINUXDEPLOY_BIN
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
LINUXDEPLOY_BIN="${LINUXDEPLOY_BIN:-$(command -v linuxdeploy || true)}"

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

# Compile schemas inside the bundle.
# کامپایل schemaها درون باندل.
glib-compile-schemas "${APPDIR}/usr/share/glib-2.0/schemas"

# Real AppRun wrapper: exports the bundle-relative schema/data/python paths so
# the application never depends on host-side installation paths.
# AppRun واقعی: مسیرهای نسبی باندل را صادر می‌کند تا برنامه هرگز به مسیرهای
# نصب میزبان وابسته نباشد.
cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
set -eu
HERE="$(dirname "$(readlink -f "${0}")")"
export GSETTINGS_SCHEMA_DIR="${HERE}/usr/share/glib-2.0/schemas"
export XDG_DATA_DIRS="${HERE}/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
# Prefer the bundled Python packages over any host installation.
# بسته‌های پایتون باندل‌شده بر نصب‌های میزبان اولویت دارند.
for candidate in "${HERE}/usr/lib/python3/dist-packages" "${HERE}/usr/lib/python3/site-packages"; do
  if [ -d "${candidate}" ]; then
    export PYTHONPATH="${candidate}${PYTHONPATH:+:${PYTHONPATH}}"
    break
  fi
done
exec "${HERE}/usr/bin/eovpn" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

# linuxdeploy is the recommended external packager. CI downloads it before
# invoking this script; if it is absent, AppDir remains available for testing.
# linuxdeploy بسته‌بند خارجی پیشنهادی است. CI آن را پیش از اجرا دانلود می‌کند؛
# اگر موجود نباشد، AppDir برای آزمایش باقی می‌ماند.
if [[ -z "${LINUXDEPLOY_BIN}" ]]; then
  echo "==> linuxdeploy not found; AppDir prepared at ${APPDIR}"
  echo "    Export LINUXDEPLOY_BIN or install linuxdeploy to produce ${OUTPUT}."
  exit 0
fi

"${LINUXDEPLOY_BIN}" --appdir "${APPDIR}" \
  --executable "${APPDIR}/usr/bin/eovpn" \
  --desktop-file "${APPDIR}/usr/share/applications/${APP_ID}.desktop" \
  --icon-file "${APPDIR}/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg" \
  --plugin gtk \
  --output appimage

echo "==> Done: ${OUTPUT}"
