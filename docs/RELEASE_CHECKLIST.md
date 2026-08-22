# 🚀 eOVPN-Pro Release Checklist
# چک‌لیست انتشار نسخه eOVPN-Pro

This runbook guides a maintainer from code freeze to a published GitHub Release
with `.deb` and Flatpak artifacts.
این راهنما نگه‌دارنده را از فریز کد تا انتشار نسخه در GitHub Release همراه با
بسته‌های `.deb` و Flatpak هدایت می‌کند.

---

## ✅ Before Release / پیش از انتشار

- [ ] `python3 -m unittest discover -s tests -v` — all green / همه تست‌ها سبز
- [ ] `python3 -m flake8 eovpn tests run_program_debug.py cffi_compile.py meson_post_install.py` — zero warnings / بدون هشدار
- [ ] `desktop-file-validate data/com.github.mahdi-arts.eovpn-pro.desktop`
- [ ] `appstreamcli validate data/com.github.mahdi-arts.eovpn-pro.metainfo.xml`
- [ ] `po/*.po` translations up-to-date / ترجمه‌ها به‌روز
- [ ] Version bumped in: `meson.build` (single source), `debian/changelog`, `eovpn-pro.spec`, `dist/rpm/eovpn-pro.spec`
  نسخه در این فایل‌ها هماهنگ شده باشد (منبع اصلی `meson.build` است)
- [ ] New changelog entry added to `metainfo.xml` `<releases>`
- [ ] `REVIEW.md` / `QA_REPORT.md` re-checked for unresolved P0/P1 items

## 📦 Build .deb Locally / ساخت بسته دبیان به‌صورت محلی

```bash
sudo apt install -y build-essential debhelper dh-python meson ninja-build \
    pkg-config python3-all python3-cffi python3-gi libnm-dev libglib2.0-dev \
    libgtk-4-dev libadwaita-1-dev libsecret-1-dev libnotify-dev gettext

dpkg-buildpackage -us -uc -b
# Output: ../eovpn-pro_1.5.0-1_amd64.deb
```

## 🧪 Smoke Test / آزمون دود

```bash
sudo dpkg -i ../eovpn-pro_1.5.0-1_amd64.deb && sudo apt install -f
eovpn --debug DEBUG
```

Verify / بررسی کنید:
- [ ] Window opens with configs list / پنجره با لیست کانفیگ باز می‌شود
- [ ] Search, filter and favorites work / جستجو، فیلتر و ستاره‌ها کار می‌کنند
- [ ] Speed test completes and sorting updates / تست سرعت تمام و مرتب‌سازی به‌روز می‌شود
- [ ] TCP/UDP filter hides the opposite transport / فیلتر TCP/UDP پروتکل مخالف را پنهان می‌کند
- [ ] Connect Fastest walks the visible list and fails over on timeout / اتصال به سریع‌ترین روی لیست نمایان حرکت می‌کند و در تایم‌اوت به بعدی می‌رود
- [ ] Connect/disconnect to a real VPN server / اتصال/قطع به یک سرور واقعی

## 📦 Build Flatpak Locally / ساخت فلت‌پک به‌صورت محلی

```bash
cd dist/flatpak
flatpak-builder --user --install --force-clean build-dir com.github.mahdi-arts.eovpn-pro.yml
flatpak run com.github.mahdi-arts.eovpn-pro
```

> The Flatpak manifest builds NetworkManager and OpenVPN 3 from source — first build takes
> a while. / مانیفست فلت‌پک NetworkManager و OpenVPN 3 را از سورس می‌سازد — ساخت اول زمان‌بر است.

## 🏷️ Publish / انتشار

```bash
git tag -a v1.5.0 -m "eOVPN-Pro 1.5.0"
git push origin v1.5.0
```

The CI pipeline (`build-deb` → `release`) attaches the `.deb` to the GitHub Release
automatically; `build-flatpak` runs on tags as well (Flatpak SDK caching enabled).
خط لوله CI به‌صورت خودکار `.deb` را به GitHub Release پیوست می‌کند و `build-flatpak`
نیز روی تگ‌ها اجرا می‌شود.

## 📋 Post-Release / پس از انتشار

- [ ] Verify the release assets on GitHub / بررسی فایل‌های پیوست‌شده
- [ ] Update the README badges/links if needed / به‌روزرسانی نشان‌ها در README در صورت نیاز
- [ ] Announce (website/social) / اطلاع‌رسانی

---

*یا علی مدد 💚*
