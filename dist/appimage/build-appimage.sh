#!/usr/bin/env bash
# ============================================================================
# eOVPN-Pro AppImage build script (experimental scaffold)
# اسکریپت ساخت AppImage برای eOVPN-Pro (زیرساخت آزمایشی)
#
# NOTE: This is a best-effort scaffold. eOVPN-Pro talks to the SYSTEM
# NetworkManager / OpenVPN 3 D-Bus services, so the produced AppImage is a
# portable UI bundle that still requires those host services to be installed.
# نکته: این یک زیرساخت «تلاش بر اساس بهترین شکل» است. برنامه با سرویس‌های
# سیستمی NetworkManager / OpenVPN 3 گفتگو می‌کند؛ بنابراین AppImage تولیدی یک
# باندل قابل‌حمل از رابط کاربری است که همچنان به نصب بودن آن سرویس‌ها نیاز دارد.
#
# Requirements / پیش‌نیازها:
#   - linuxdeploy (https://github.com/linuxdeploy/linuxdeploy/releases)
#   - linuxdeploy-plugin-gtk (https://github.com/linuxdeploy/linuxdeploy-plugin-gtk)
#   - linuxdeploy-plugin-python (https://github.com/linuxdeploy/linuxdeploy-plugin-python)
#   - A Python venv with PyGObject + cffi (pip install -r requirements.txt)
# ============================================================================
set -euo pipefail

APP_NAME="eOVPN-Pro"
APP_ID="com.github.mahdi-arts.eovpn-pro"
VERSION="1.5.0"
APPDIR="$(pwd)/AppDir"
export ARCH="${ARCH:-x86_64}"

echo "==> [eOVPN-Pro] Preparing AppDir at ${APPDIR}"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share"

# 1. Python entry wrapper / نقطه ورود پایتون
cat > "${APPDIR}/usr/bin/eovpn" <<EOF
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib", "python"))
os.environ.setdefault("GSETTINGS_SCHEMA_DIR", "/usr/share/glib-2.0/schemas")
from eovpn.application import launch_eovpn
sys.exit(launch_eovpn())
EOF
chmod +x "${APPDIR}/usr/bin/eovpn"

# 2. Desktop entry + icon / فایل دسکتاپ و آیکون
cp "data/${APP_ID}.desktop" "${APPDIR}/usr/share/"
cp "data/icons/${APP_ID}.svg" "${APPDIR}/usr/share/"

# 3. Bundle Python packages (requires an active venv with the deps installed)
#    باندل پکیج‌های پایتون (نیازمند venv فعال با وابستگی‌های نصب‌شده)
if [ -n "${VIRTUAL_ENV:-}" ]; then
  mkdir -p "${APPDIR}/usr/lib/python"
  cp -r "${VIRTUAL_ENV}/lib/python"*"/site-packages/eovpn" "${APPDIR}/usr/lib/python/" 2>/dev/null || true
  cp -r eovpn "${APPDIR}/usr/lib/python/"
fi

# 4. linuxdeploy + GTK plugin + Python plugin
export LDAI_OUTPUT="eovpn-pro-${VERSION}-${ARCH}.AppImage"
linuxdeploy --appdir "${APPDIR}" \
  --plugin gtk \
  --plugin python \
  --output appimage

echo "==> Done: ${LDAI_OUTPUT}"
