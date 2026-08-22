# 🖥️ AppImage (Experimental / آزمایشی)

**Status: NOT production-ready — experimental scaffold only.**
**وضعیت: آماده تولید نیست — فقط زیرساخت آزمایشی.**

## Why is this hard? / چرا سخت است؟

eOVPN-Pro is a GTK4 + PyGObject + CFFI application that manages VPN tunnels
through the **system** NetworkManager / OpenVPN 3 D-Bus services. A portable
AppImage would bundle the UI stack (Python, GTK, Libadwaita, native CFFI
bindings) but would still need those host services installed.

eOVPN-Pro یک برنامه GTK4 + PyGObject + CFFI است که تونل‌های VPN را از طریق
سرویس‌های **سیستمی** NetworkManager / OpenVPN 3 مدیریت می‌کند. AppImage
قابل‌حمل می‌تواند پشته رابط کاربری را باندل کند ولی همچنان به نصب بودن آن
سرویس‌ها روی میزبان نیاز دارد.

## Build / ساخت

```bash
# 1. Create a venv with the runtime deps / ساخت venv با وابستگی‌های زمان اجرا
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Download linuxdeploy + plugins / دانلود ابزارهای linuxdeploy
#    https://github.com/linuxdeploy/linuxdeploy/releases
#    https://github.com/linuxdeploy/linuxdeploy-plugin-gtk/releases
#    https://github.com/linuxdeploy/linuxdeploy-plugin-python/releases

# 3. Build / ساخت
source .venv/bin/activate
bash dist/appimage/build-appimage.sh
```

## Limitations / محدودیت‌ها

- Requires host NetworkManager + `network-manager-openvpn` plugin.
  نیازمند NetworkManager میزبان و افزونه openvpn آن.
- Requires host GNOME Keyring (Secret Service) for credential storage.
  نیازمند کی‌رینگ GNOME میزبان برای ذخیره امن اعتبارنامه‌ها.
- Native `libeovpn_nm.so` / `_libeovpn_nm.so` must be built (meson) and bundled.
  کتابخانه‌های بومی باید با meson ساخته و باندل شوند.
- Not wired into CI yet. / هنوز به CI متصل نشده است.

*یا علی مدد 💚*
