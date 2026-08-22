# 📜 eOVPN-Pro Changelog
# فهرست تغییرات نسخه‌های eOVPN-Pro

All notable changes are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/).
همه تغییرات مهم در اینجا ثبت می‌شوند؛ قالب بر اساس استاندارد Keep a Changelog است.

## [Unreleased]

### Added / افزوده‌شده
- **Continuous integration** — `.github/workflows/ci.yml`: Ruff lint and format check, mypy,
  the 56 offline unit tests across Python 3.10/3.11/3.12, coverage of the pure modules,
  `pip-audit --strict`, metadata consistency, a full Meson build with desktop/AppStream
  validation, and smoke builds of the `.deb`, `.rpm` and Arch packages (Debian native,
  Fedora and Arch containers).
  **یکپارچه‌سازی مداوم** — ورک‌فلوی `ci.yml`: لینت و بررسی قالب‌بندی Ruff، بررسی نوع mypy،
  اجرای ۵۶ تست واحد آفلاین روی پایتون ۳٫۱۰ تا ۳٫۱۲، پوشش ماژول‌های خالص، `pip-audit --strict`،
  بررسی یکپارچگی متادیتا، ساخت کامل Meson با اعتبارسنجی desktop و AppStream، و ساخت آزمایشی
  بسته‌های `.deb`، `.rpm` و آرچ (به‌صورت بومی دبیان و کانتینر فدورا/آرچ).
- **CodeQL static analysis** — `.github/workflows/codeql.yml` runs the security-extended query
  packs against the Python codebase and the compiled C bindings on every push, pull request
  and weekly. / **تحلیل ایستای CodeQL** — وورک‌فلوی `codeql.yml` پکیج‌های پرس‌وجوی
  security-extended را روی کدبیس پایتون و بایندینگ‌های C در هر push، pull request و هفتگی اجرا می‌کند.
- **Release automation** — `.github/workflows/release.yml` builds all five package formats
  (`.deb`, `.rpm`, `.pkg.tar.zst`, AppImage, Flatpak) on a version tag, verifies that every
  packaging file declares the same version as the tag, attaches build-provenance attestations
  to the `.deb` and AppImage, generates a `SHA256SUMS` manifest and publishes the GitHub
  Release with auto-generated notes.
  **انتشار خودکار** — ورک‌فلوی `release.yml` با ایجاد تگ نسخه، هر پنج قالب بسته را می‌سازد،
  یکسان بودن نسخه در همهٔ فایل‌های بسته‌بندی را بررسی می‌کند، گواهی provenance به `.deb` و
  AppImage ضمیمه می‌کند، فایل `SHA256SUMS` را تولید می‌کند و نسخه را با یادداشت‌های خودکار
  منتشر می‌سازد.
- **Arch Linux packaging** — `dist/arch/PKGBUILD` and `dist/arch/.SRCINFO`. The recipe is
  dual-mode: it builds the working tree when run inside a checkout, or downloads the tagged
  release tarball when used standalone (AUR).
  **بسته‌بندی آرچ‌لینوکس** — فایل‌های `dist/arch/PKGBUILD` و `dist/arch/.SRCINFO`. این دستور
  دو حالته است: داخل مخزن، درخت کاری را می‌سازد و به‌صورت مستقل (AUR) آرشیو نسخهٔ تگ‌خورده
  را دانلود می‌کند.
- **RPM helper script** — `scripts/build-rpm.sh` mirrors `build-deb.sh`/`build-flatpak.sh` for
  local Fedora/RHEL/openSUSE builds. / **اسکریپت کمکی RPM** — `scripts/build-rpm.sh` هم‌تراز
  اسکریپت‌های deb و Flatpak برای ساخت محلی در فدورا/RHEL/openSUSE.
- **Debian autopkgtest** — `debian/tests/` runs a headless smoke test (binary `--help`,
  desktop/schema validation) after installation. / **autopkgtest دبیان** — `debian/tests/`
  آزمون دود بدون نمایشگر (اجرای `--help` و اعتبارسنجی desktop/schema) را پس از نصب اجرا می‌کند.
- Offline smoke tests for import-safe pure modules. / تست‌های دود برای ماژول‌های خالص قابل ایمپورت.

### Changed / تغییر یافته
- **Cascade state machine extracted** — `eovpn/cascade_controller.py` owns the full
  connect-to-fastest lifecycle; `MainWindow` now delegates to it (composition over
  inheritance, `Gtk.Builder` via composition). Unit-testable with a fake host/scheduler.
  **استخراج ماشین حالت آبشار** — `eovpn/cascade_controller.py` مالک چرخه کامل اتصال به
  سریع‌ترین است؛ `MainWindow` اکنون به آن واگذار می‌کند (ترکیب به‌جای وراثت و استفاده از
  `Gtk.Builder` به‌صورت ترکیبی). با میزبان/زمان‌بند جعلی قابل تست واحد است.
- **Bandwidth monitor extracted** — `eovpn/network_monitor.py` reads `/proc/net/dev` in a
  single pass per tick. / **استخراج مانیتور پهنای باند** — `eovpn/network_monitor.py` در هر
  تیک فقط یک‌بار `/proc/net/dev` را می‌خواند.
- **Typed connection events** — `eovpn/events.py` normalizes the legacy callback payloads;
  `on_connection_event` no longer branches on `type(result)`.
  **رویدادهای تایپ‌شده اتصال** — `eovpn/events.py` payloadهای قدیمی را نرمال می‌کند؛
  `on_connection_event` دیگر روی `type(result)` شاخه‌بندی نمی‌کند.
- **Version-tolerant dialogs** — `eovpn/ui_compat.py` prefers `Gtk.AlertDialog`/`Gtk.FileDialog`
  with fallbacks for older GTK4 runtimes; deprecated `hide()/show()` calls replaced by
  `set_visible()`. / **دیالوگ‌های مقاوم به نسخه** — `eovpn/ui_compat.py` ویجت‌های مدرن را با
  fallback برای رانتایم‌های قدیمی ترجیح می‌دهد و `hide()/show()` منسوخ با `set_visible()`
  جایگزین شد.
- Backend versions are probed via lightweight `probe_version()` classmethods instead of
  instantiating backends on the UI thread. / نسخه بک‌اندها با `probe_version()` سبک به‌جای
  نمونه‌سازی روی نخ UI خوانده می‌شود.
- NetworkManager connect/disconnect now run on a daemon worker thread, so the nested
  `GMainLoop` can never freeze the UI. / اتصال/قطع NetworkManager اکنون روی نخ کارگر اجرا
  می‌شود تا `GMainLoop` تودرتو هرگز UI را فریز نکند.
- OTP dialog supports pasting a full 6-digit code. / دیالوگ OTP چسباندن کد کامل ۶ رقمی را
  پشتیبانی می‌کند.

### Security / امنیت
- Remote configuration sources now require HTTPS; HTTP URLs and non-HTTPS redirects are rejected.
  منابع کانفیگ راه‌دور اکنون حتماً باید HTTPS باشند؛ HTTP و ریدایرکت غیر HTTPS رد می‌شود.
- Configuration sources on localhost or literal private/loopback/reserved IP addresses are now
  refused outright (SSRF hardening); unresolved hostnames still get a warning only.
  منابع کانفیگ روی localhost یا IPهای صریح خصوصی/loopback/رزرو اکنون قاطعانه رد می‌شوند
  (سخت‌سازی SSRF)؛ نام‌های میزبان حل‌نشده همچنان فقط هشدار می‌گیرند.
- The `cffi` floor was raised to `>=1.16.0` so the resolver can never pick 1.15.0
  (CVE-2023-23931). / کف `cffi` به `>=1.16.0` رسید تا حل‌کننده هرگز 1.15.0
  (CVE-2023-23931) را انتخاب نکند.
- In-RAM session passwords are now stored as mutable `bytearray`s and actively zeroed on
  clear. / رمز نشست در RAM اکنون به‌صورت `bytearray` تغییرپذیر ذخیره و هنگام پاک‌سازی فعالانه
  صفر می‌شود.
- ZIP extraction now enforces private file permissions, rejects symlinks/duplicate basenames
  and limits the number of archive entries. / استخراج ZIP اکنون مجوز فایل خصوصی اعمال می‌کند،
  symlink و نام تکراری را رد می‌کند و تعداد ورودی‌ها را محدود می‌سازد.
- NetworkManager profiles are marked as eOVPN-managed; delete/status operations avoid other VPNs.
  پروفایل‌های NetworkManager به‌عنوان متعلق به eOVPN علامت‌گذاری می‌شوند تا عملیات حذف/وضعیت
  به VPNهای دیگر آسیب نزند.
- NetworkManager import now aborts if the agent-owned password secret flag cannot be set.
  اگر پرچم agent-owned رمز عبور قابل تنظیم نباشد، import متوقف می‌شود.
- Fixed a latent use-after-free contract in `eovpn_get_managed_active_connection` (only the
  duplicated UUID now escapes the NMClient scope) and a per-call GVariant leak in
  `_get_all_sessions`. / قرارداد use-after-free نهفته در `eovpn_get_managed_active_connection`
  (اکنون فقط UUID کپی‌شده از محدوده NMClient خارج می‌شود) و نشت GVariant در هر فراخوانی
  `_get_all_sessions` اصلاح شد.
- Removed the process-wide `UniqueSession` state from the OpenVPN 3 binding: every session
  operation now takes the session path explicitly (thread-safe, multi-session capable).
  وضعیت سراسری `UniqueSession` از بایندینگ OpenVPN 3 حذف شد؛ هر عملیات نشست اکنون مسیر
  نشست را صریحاً می‌گیرد (thread-safe و چندنشسته).
- Dependency CVE scanning (`pip-audit --strict`) and CodeQL static analysis now run on every
  push and pull request, so a vulnerable dependency blocks the merge gate.
  پویش CVE وابستگی‌ها و تحلیل ایستای CodeQL اکنون در هر push و pull request اجرا می‌شوند و
  وجود وابستگی آسیب‌پذیر مانع عبور از دروازهٔ ادغام می‌شود.
- Releases now ship a `SHA256SUMS` manifest so downloads can be verified before installation.
  انتشارها اکنون فایل `SHA256SUMS` دارند تا فایل دانلودشده پیش از نصب راستی‌آزمایی شود.

### Fixed / رفع‌شده
- All OpenVPN 3 native D-Bus calls now use bounded timeouts. / همه تماس‌های بومی OpenVPN 3 D-Bus
  تایم‌اوت محدود دارند.
- D-Bus subscriptions are explicitly tracked and cleaned up. / اشتراک‌های D-Bus صریحاً رهگیری و پاک می‌شوند.
- Backend switching stops the old watcher before replacing it. / تعویض بک‌اند قبل از جایگزینی، watcher قبلی را متوقف می‌کند.
- AppImage build script now installs through Meson and places desktop/icon/schema assets correctly.
  اسکریپت ساخت AppImage از طریق Meson نصب می‌کند و فایل‌های desktop، icon و schema را درست قرار می‌دهد.

### Documentation / مستندات
- `README.md`, `PACKAGING.md` and `SECURITY.md` no longer describe CI/CD, package formats or
  security scanning that did not exist. Every claim is now backed by a file in the repository,
  and the test count is stated accurately (56).
  فایل‌های `README.md` و `PACKAGING.md` و `SECURITY.md` دیگر قابلیت‌های موجود نبودهٔ CI/CD،
  قالب‌های بسته و پویش امنیتی را توصیف نمی‌کنند. اکنون هر ادعا به یک فایل واقعی در مخزن متکی
  است و تعداد تست‌ها دقیق (۵۶) ذکر شده است.
- Installation instructions added for all five package formats, plus a format support matrix.
  دستور نصب برای هر پنج قالب بسته و یک جدول وضعیت پشتیبانی قالب‌ها افزوده شد.
- Known limitations are now documented explicitly, including the absence of a kill-switch and
  DNS-leak protection. / محدودیت‌های شناخته‌شده از جمله نبود kill-switch و محافظت نشت DNS صریحاً
  مستند شدند.

## [1.5.0] — 2026-08-22

### Added / افزوده‌شده
- Full Persian (Farsi) RTL localization with dynamic language switching (English/Persian).
  ترجمه کامل فارسی، چیدمان راست‌به‌چپ و تغییر پویای زبان بین فارسی و انگلیسی.
- Concurrent multi-threaded TCP latency testing and dynamic latency-based sorting.
  تست تأخیر TCP هم‌زمان و چندنخی و مرتب‌سازی پویا بر اساس کمترین پینگ.
- Cascading "Connect Fastest" that walks the sorted/filtered list with adaptive handshake timeouts.
  اتصال آبشاری به سریع‌ترین سرور با تایم‌اوت تطبیقی روی لیست مرتب و فیلترشده.
- Live server search, smart filters (All/Favorites/Online/Offline), TCP/UDP protocol filter and favorites.
  جستجوی زنده، فیلتر هوشمند، فیلتر پروتکل TCP/UDP و سرورهای موردعلاقه.
- Real-time bandwidth monitor reading `/proc/net/dev` for VPN interfaces.
  نمایشگر زنده پهنای باند از شمارنده‌های هسته برای اینترفیس‌های VPN.
- OpenVPN 3 Data Channel Offload (DCO) toggle in the Backend settings tab.
  کلید شتاب‌دهنده DCO سرویس OpenVPN 3 در برگه تنظیمات بک‌اند.
- Local folder & ZIP import with Zip-Slip / zip-bomb / size-cap protection.
  ایمپورت پوشه محلی و ZIP با محافظت Zip-Slip، بمب فشرده و سقف حجم.
- Security audit warning for imported configs containing executable OpenVPN directives.
  هشدار ممیزی امنیتی برای کانفیگ‌های واردشده دارای دایرکتیوهای اجرایی OpenVPN.
- Staging (atomic) config downloads so a failed update never destroys existing configs.
  دانلود مرحله‌ای و جایگزینی اتمی تا خطای به‌روزرسانی هرگز کانفیگ‌های قبلی را از بین نبرد.
- Local quality tooling: offline unit-test suite, lint/type-check configuration, dependency audit
  configuration and the `scripts/check_project_meta.py` metadata consistency checker.
  ابزارهای کیفیت محلی: مجموعه تست واحد آفلاین، پیکربندی لینت و بررسی نوع، پیکربندی ممیزی
  وابستگی‌ها و اسکریپت `scripts/check_project_meta.py` برای بررسی یکپارچگی متادیتا.
  > Note: the GitHub Actions pipeline itself landed after 1.5.0 — see `[Unreleased]`.
  > نکته: خود خط لوله GitHub Actions پس از نسخهٔ ۱٫۵٫۰ اضافه شد؛ به بخش `[Unreleased]` مراجعه کنید.

### Security / امنیت
- OTP values are never logged. / کدهای یک‌بارمصرف هرگز لاگ نمی‌شوند.
- "Delete All VPN Connections" requires explicit confirmation.
  حذف همه اتصالات VPN نیازمند تأیید صریح کاربر است.
- Passwords are stored in the Secret Service with an agent-owned flag so NetworkManager
  never writes them to disk. / رمزها در Secret Service با پرچم agent-owned ذخیره می‌شوند
  و NetworkManager آن‌ها را روی دیسک نمی‌نویسد.
- Hard 15-second timeouts on all D-Bus/NetworkManager operations (no more UI freezes).
  تایم‌اوت سخت ۱۵ ثانیه‌ای برای همه عملیات D-Bus/NetworkManager (بدون قفل رابط کاربری).
- GTK widgets are only touched from the main thread (fixed worker-thread access).
  دسترسی به ویجت‌های GTK فقط از نخ اصلی (رفع دسترسی از نخ کارگر).

### Changed / تغییر یافته
- `SettingsWindow.setup()` and `MainWindow.setup()` split into focused builder methods.
  متدهای setup پنجره‌ها به سازنده‌های تخصصی کوچک‌تر تقسیم شدند.
- Single source of truth for the RPM spec at `dist/rpm/eovpn-pro.spec`.
  منبع واحد مشخصات RPM در مسیر dist/rpm/eovpn-pro.spec.
- Shared `.ovpn` parser (DRY) and shared CFFI string mixin for both backends.
  پارسر مشترک فایل‌های .ovpn و میکسین مشترک CFFI برای هر دو بک‌اند.
- Man page (`eovpn.1`) installed by Meson; `meson test` runs the unit suite.
  صفحه راهنمای eovpn.1 نصب می‌شود و دستور meson test تست‌ها را اجرا می‌کند.

### Fixed / رفع‌شده
- Off-by-one in last-connected cursor restore. / خطای off-by-one در نشانگر آخرین اتصال.
- `AUTH_USER=None` crash in the OpenVPN 3 attention handler. / رفع کرش وقتی نام کاربری تنظیم نشده است.
- IP lookup UI updates now run on the main thread. / به‌روزرسانی رابط استعلام IP در نخ اصلی.
- `extract_enums.py` writes with truncation (no duplicate `#define`s).
  اسکریپت extract_enums با حالت نوشتن از ابتدا اجرا می‌شود (بدون تعریف تکراری).
- GPL-3.0 license shown in the About dialog. / نمایش مجوز GPL-3.0 در دیالوگ درباره.

## [1.5] — 2026-08-05

### Added
- Persian (Farsi) localization with RTL support. / محلی‌سازی فارسی با پشتیبانی RTL.
- Redesigned connection details card (fixed-size, no window jitter).
  بازطراحی کادر جزئیات اتصال با ابعاد ثابت (بدون لرزش پنجره).
- Backend settings tab redesign and OpenVPN 3 DCO support.
  بازطراحی تب تنظیمات بک‌اند و پشتیبانی از DCO.

## [1.4] — 2025-10-15

### Added
- Pro edition branding. / برندینگ نسخه حرفه‌ای.
- Multi-threaded TCP ping/speed test and speed-based sorting.
  تست پینگ TCP چندنخی و مرتب‌سازی بر اساس سرعت.
- "Select Fastest" automated utility. / ابزار خودکار انتخاب سریع‌ترین سرور.

[Unreleased]: https://github.com/Mahdi-Arts/eOVPN-Pro/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/Mahdi-Arts/eOVPN-Pro/releases/tag/v1.5.0
