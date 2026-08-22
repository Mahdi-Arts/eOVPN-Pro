# Flatpak

## Notes / نکات

- The manifest (`com.github.mahdi-arts.eovpn-pro.yml`) builds NetworkManager, libnma,
  polkit, udev, libndp and OpenVPN 3 Linux from source so the sandbox can manage VPN
  connections without host privileges.
  مانیفست، NetworkManager، libnma، polkit، udev، libndp و OpenVPN 3 Linux را از سورس
  می‌سازد تا سندباکس بتواند بدون نیاز به دسترسی ریشه، اتصالات VPN را مدیریت کند.
- `runtime-version: '50'` must match a runtime available on Flathub; bump it when the
  GNOME runtime is updated. / `runtime-version: '50'` باید با رانتایم موجود در فلاتهاب
  هماهنگ باشد؛ هنگام ارتقای رانتایم GNOME آن را به‌روزرسانی کنید.
- The OpenVPN 3 Python bindings are required at configure time for the DCO backend;
  the `python3-cffi.json` module installs `cffi`, and the openvpn3-linux build provides
  the `openvpn3` Python package used by `extract_enums.py`.
  بایندینگ پایتون OpenVPN 3 هنگام پیکربندی برای بک‌اند DCO لازم است.
- Build locally with:
  ```sh
  cd dist/flatpak
  flatpak-builder --user --install --force-clean build-dir com.github.mahdi-arts.eovpn-pro.yml
  flatpak run com.github.mahdi-arts.eovpn-pro
  ```
