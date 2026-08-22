# Flatpak staging / آماده‌سازی Flatpak

## English

The upstream manifest builds the current checkout for QA. It deliberately
supports the **NetworkManager backend only** and talks to the host
`org.freedesktop.NetworkManager` service through a narrow D-Bus permission.
The host must provide:

- NetworkManager;
- `NetworkManager-openvpn` (the service-side OpenVPN plugin);
- a working desktop Secret Service for persistent passwords.

The sandbox bundles a pinned `libnm` and the non-GUI OpenVPN import plugin so
`.ovpn` parsing is deterministic. It does **not** run a second NetworkManager or
OpenVPN daemon inside the sandbox. File selection uses the desktop portal and
imported files stay in the Flatpak-private configuration directory.

Build locally:

```bash
cd dist/flatpak
flatpak install --user flathub org.gnome.Sdk//50 org.gnome.Platform//50
flatpak-builder --user --install --force-clean \
  build-dir io.github.Mahdi_Arts.eOVPN_Pro.yml
flatpak run io.github.Mahdi_Arts.eOVPN_Pro
```

Before submitting to Flathub, replace the final `type: dir` source with the
signed `v1.5.0` release archive and its SHA-256. The release workflow generates
a ready-to-review manifest copy after the tag exists.

## فارسی

مانیفست بالادستی برای کنترل کیفیت، Checkout جاری را می‌سازد و عمداً فقط از
بک‌اند **NetworkManager** پشتیبانی می‌کند. ارتباط با سرویس
`org.freedesktop.NetworkManager` میزبان از طریق مجوز محدود D-Bus انجام می‌شود.
میزبان باید NetworkManager، افزونه سرویس `NetworkManager-openvpn` و یک Secret
Service دسکتاپ فعال داشته باشد.

در Sandbox نسخه Pinشده `libnm` و افزونه بدون رابط گرافیکی Import قرار می‌گیرد تا
پارس فایل `.ovpn` بازتولیدپذیر باشد. هیچ NetworkManager یا OpenVPN Daemon دومی
داخل Sandbox اجرا نمی‌شود. انتخاب فایل از Portal دسکتاپ انجام شده و فایل‌های
واردشده در پوشه خصوصی Flatpak باقی می‌مانند.

پیش از ارسال به Flathub، Source نهایی از نوع `dir` باید با آرشیو امضاشده نسخه
`v1.5.0` و SHA-256 آن جایگزین شود. Workflow انتشار پس از ایجاد Tag، نسخه مناسب
بازبینی مانیفست را تولید می‌کند.
