# 🔍 بررسی فنی و موشکافانه مخزن eOVPN-Pro (نسخه 1.5.0)

**تاریخ بررسی:** 2026-08-22 — **شاخه بررسی‌شده:** `master` (کامیت `3b2330c`)
**ابزارها:** تحلیل دستی کد + اجرای تست‌ها + بررسی بسته‌بندی و متادیتا + بررسی مخزن گیت‌هاب

> خلاصه اجرایی: پروژه‌ای تمیز، خوش‌ساختار و امنیت‌محور با معماری ماژولار و دو بک‌اند
> (NetworkManager و OpenVPN 3). ۱۲ تست واحد همگی پاس می‌شوند، کد بدون خطای کامپایل
> پایتون است، و زیرساخت بسته‌بندی (.deb/.rpm/Flatpak) تقریباً کامل است. مهم‌ترین نقاط
> ضعف: چند باگ امنیتی/منطقی کوچک (لاگ OTP، حذف بی‌تأیید همه اتصالات VPN، خطای off-by-one)،
> فقدان CI فعال، و نبود زیرساخت AppImage.

---

## ۱. تحلیل معماری و ساختار

### نمای کلی

| جنبه | وضعیت |
|---|---|
| زبان/UI | Python 3.10+ + GTK4 + Libadwaita |
| سیستم ساخت | Meson + Ninja (+ CFFI برای بایندینگ C) |
| بک‌اندها | NetworkManager (از طریق بایندینگ CFFI روی libnm) و OpenVPN 3 Linux (D-Bus + C) |
| محلی‌سازی | gettext با ۴ زبان: انگلیسی، فارسی (با RTL)، ایتالیایی، پرتغالی برزیل |
| تست | unittest — ۱۲ تست آفلاین |
| مجوز | GPL-3.0 |

### سازمان‌دهی فایل‌ها — امتیاز مثبت ✅

```
eovpn/
├── application.py          # نقطه ورود، آرگومان‌های خط فرمان، i18n، RTL
├── eovpn_base.py           # کلاس پایه، تنظیمات GSettings، اعلان‌ها، ذخیره امن رمز در RAM
├── main_window.py          # پنجره اصلی (۹۱۶ خط — کمی حجیم)
├── settings_window.py      # پنجره تنظیمات
├── connection_manager.py   # انتزاع ConnectionManager + دو پیاده‌سازی
├── speed_test.py           # تست پینگ TCP موازی (ThreadPool)
├── utils.py                # ZIP امن (Zip-Slip)، دانلود، تشخیص auth-user-pass
├── ip_lookup/lookup.py     # استعلام IP/کشور با HTTPS و fallback سه‌گانه
├── dialogs/otp.py          # دیالوگ ۲FA/OTP شش‌رقمی
└── backend/
    ├── networkmanager/     # بایندینگ CFFI + شنونده D-Bus
    └── openvpn3/           # بایندینگ CFFI + D-Bus (OTP، DCO، Attention)
subprojects/                # کد C: eovpn_nm.c (434 خط) و openvpn3.c (681 خط)
data/                       # gresource، آیکون‌ها، ۲۵۶ پرچم SVG، فایل‌های UI
po/                         # ترجمه‌ها
debian/، dist/rpm، dist/flatpak، dist/ci   # بسته‌بندی
tests/                      # تست‌های واحد
```

نکات مثبت معماری:
- **انتزاع درست**: کلاس انتزاعی `ConnectionManager` با متدهای `connect/disconnect/status/version` و دو پیاده‌سازی مستقل — افزودن بک‌اند سوم (مثلاً WireGuard) بسیار ساده است.
- **تفکیک لایه‌ها**: UI (main/settings) از منطق (connection_manager/speed_test/utils/lookup) جدا شده؛ ماژول‌های خالص (speed_test، utils، lookup) بدون وابستگی به GTK هستند و به همین دلیل تست‌پذیرند.
- **منابع GTK در gresource**: فایل‌های UI/CSS/آیکون/پرچم داخل یک باندل gresource — نصب تمیز و سریع.
- **بایندینگ C بومی**: تعامل با libnm و سرویس openvpn3 در C انجام می‌شود و از طریق CFFI به پایتون وصل شده — انتخاب معقول برای APIهای غیر-GObject.
- **امنیت در طراحی**: Secret Service (Keyring) برای رمز، فایل موقت 0600، محافظت Zip-Slip — اینها در سطح طراحی دیده شده‌اند، نه وصله‌کاری.

نقاط ضعف معماری:
1. **الگوی Service-Locator سراسری**: ماژول `eovpn_base.py` از دیکشنری‌های سراسری (`_storage_record`، `_builder_record`، `_session_secrets`) به‌عنوان حافظه مشترک استفاده می‌کند. این الگو تست‌پذیری را کم می‌کند، state را پنهان می‌کند و با چند-پنجره‌ای شدن برنامه مشکل پیدا می‌کند.
2. **`MainWindow` ۹۱۶ خطی و `SettingsWindow` ۵۳۸ خطی**: این دو کلاس همه‌چیز را انجام می‌دهند (ساخت ویجت، اکشن‌ها، منو، رویدادها). تفکیک به ویجت‌های کوچک‌تر نگهداری را ساده‌تر می‌کند.
3. **کلاس `Signals` تکراری**: در `main_window.py` و `settings_window.py` دو کلاس مجزا با همین نام وجود دارد — هم‌نامی و تکرار کد.
4. **ناسازگاری جزئی**: `eovpn/backend/networkmanager/` فایل `__init__.py` ندارد (پکیج namespace) ولی `backend/openvpn3/` دارد — هرچند کار می‌کند، ناسازگار است.
5. **نسخه‌ها چندگانه‌اند**: meson `1.5`، README و changelog `1.5.0`، metainfo `1.5` و `APP_VERSION` در metadata.json `1.5` — همه تقریباً هماهنگ ولی بهتر است یک منبع واحد (مثلاً meson.project_version) باشد.

---

## ۲. بررسی کیفیت کد (Code Quality)

### موارد مثبت ✅
- **داک‌استرینگ‌های دوزبانه** (فارسی/انگلیسی) در همه ماژول‌ها — بسیار خوب و کمیاب.
- **تایپ‌هینت مدرن** (`str | None`، `dict[str, float]`) — نیازمند پایتون 3.10+ (در CI از 3.11 استفاده شده).
- **مدیریت خطا**: تقریباً همه مسیرهای I/O و D-Bus در try/except هستند و به‌جای crash، لاگ می‌شوند.
- **تست‌های واحد معنادار**: تست Zip-Slip، تست fallback سرویس‌های IP، تست پارس `remote` و پینگ با mock — ۱۲ تست، همه پاس ✅ (اجرا شد و `OK` بود).
- **استایل C تمیز**: رعایت GNU style با `.clang-format`، بررسی `GError` در اکثر نقاط، مدیریت حافظه با `g_free`/`g_object_unref`.
- **لاگینگ منظم** با logger استاندارد پایتون و سطح‌بندی درست.
- **کامپایل پایتون بدون خطا** (`py_compile` روی همه فایل‌ها پاس شد).

### مشکلات و پیشنهادها ⚠️
1. **دسترسی به ویجت‌های GTK از نخ کارگر** — `main_window.update_set_ip_flag()` از داخل یک `threading.Thread` روی ویجت‌ها (`set_pixbuf`، `set_label`، `spinner.start/stop`) کار می‌کند. GTK **نخ‌امن نیست**؛ این کار باید با `GLib.idle_add` به نخ اصلی برگردانده شود. امروز «اغلب کار می‌کند»، فردا crash تصادفی می‌دهد.
2. **باگ off-by-one در نشانگر آخرین اتصال** — در `main_window.py`:
   ```python
   self.set_setting(self.SETTING.LAST_CONNECTED_CURSOR, configs.index(selected_cfg) - 1)
   ```
   بعداً `select_row(rows[cur])` با همان مقدار انجام می‌شود؛ یعنی همیشه یک ردیف **بالاتر** از کانفیگ واقعی انتخاب می‌شود و برای ایندکس ۰ (index-1=-1) اصلاً انتخاب نمی‌شود. باید `index` (بدون منها) ذخیره شود.
3. **باگ احتمالی در بک‌اند OpenVPN3** — در `backend/openvpn3/dbus.py`:
   ```python
   self.get_setting(self.SETTING.AUTH_USER).encode("utf-8")
   ```
   اگر `auth-user` تنظیم نشده باشد (`None`)، `AttributeError` در کالبک سیگنال D-Bus رخ می‌دهد. باید `or ""` یا بررسی None شود.
4. **ژنراتور `enums.h` ناامن برای build مکرر** — `extract_enums.py` با حالت `"a+"` (append) می‌نویسد؛ اجرای دوباره meson بدون حذف فایل، تعریف‌های تکراری `#define` تولید می‌کند که می‌تواند خطای کامپایل C بدهد (اسکریپت debug این فایل را حذف می‌کند ولی meson setup دوباره نه). حالت `"w"` + یک منبع واحد بهتر است.
5. **کلیدهای تنظیمات مرده**: `update-on-start`، `connect-on-launch`، `current-connected`، `remote-type`، `remote-savepath`، `ca-set-explicit` و `auth-pass` در gschema تعریف شده‌اند اما هیچ‌جا در کد خوانده/نوشته نمی‌شوند — بهتر است حذف یا پیاده‌سازی شوند.
6. **ناسازگاری مجوز در About Dialog**: `Gtk.License.LGPL_3_0` استفاده شده در حالی که LICENSE پروژه GPL-3.0 است — باید `GPL_3_0` باشد.
7. **نکات ریز**: نام کلاس `eovpn` با حرف کوچک؛ `import time as pytime` داخل تابع؛ `sys.argv.remove("-c")` دستکاری خام آرگومان‌ها؛ سانتی‌نل عجیب رشته `"null"` در `get_setting` (اگر کاربر واقعاً مقدار `"null"` ذخیره کند None برمی‌گردد)؛ `cffi_compile.py` گزینه `-Wl,-rpath=$ORIGIN,-I<header>` دارد که `-I` در آن بیربط است.
8. **غیبت ابزارهای کیفیت در CI**: flake8 در CI نصب می‌شود ولی اجرا نمی‌شود؛ نه mypy دارید نه ruff؛ پیشنهاد: اجرای `flake8` + `mypy` در workflow و افزودن فایل تنظیمات.

---

## ۳. بررسی امنیت و شبکه

### نقاط قوت — واقعاً خوب طراحی شده ✅
- **رمز عبور در دیسک نمی‌رود**: ذخیره در Secret Service (libsecret با Schema امن) + fallback در RAM نوسان‌پذیر پروسه (`_session_secrets`)؛ هیچ‌جا در dconf/فایل نوشته نمی‌شود. اسکن مخزن هم هیچ کلید/توکن/رمز جاسازی‌شده‌ای نشان نداد.
- **فایل موقت امن**: `NamedTemporaryFile` + `chmod 0o600` + حذف در `finally` — در برابر race condition و باقی‌ماندن رمز روی دیسک درست کار شده.
- **محافظت Zip-Slip**: مسطح‌سازی `basename` + `is_safe_path` با `realpath` + `commonpath` + **تست واحد اختصاصی** — مثال خوبی از امنیتِ همراهِ آزمون.
- **استعلام IP فقط HTTPS** با سه ارائه‌دهنده جایگزین (Cloudflare، ipapi.co، ipify) و timeout — خوب.
- **اعتبارسنجی scheme دانلود**: فقط `http`/`https` پذیرفته می‌شود.
- **D-Bus با policy سیستم**: سرویس‌های openvpn3 با `--system-talk-name` محدود به نام‌های لازم در Flatpak.

### آسیب‌پذیری‌ها و ریسک‌ها ⚠️
| شدت | مورد |
|---|---|
| متوسط | **لاگ شدن OTP**: در `backend/openvpn3/dbus.py:99` — `logger.info("sending OTP: %s", otp)` کد یکبارمصرف ۲FA را در لاگ می‌نویسد. OTPها نباید هرگز لاگ شوند. (همین‌طور رمز عبور — که فعلاً لاگ نمی‌شود ✅) |
| متوسط | **دکمه «Delete All VPN Connections!»** تمام پروفایل‌های VPN سامانه (هر اپلیکیشنی — OpenVPN، WireGuard و…) را از NetworkManager **بدون هیچ دیالوگ تأییدی** حذف می‌کند. باید confirmation dialog داشته باشد یا فقط UUIDهای متعلق به خودش را حذف کند. |
| پایین-متوسط | **کلید مرده `auth-pass` در gschema**: کد فعلی از آن استفاده نمی‌کند (خوب)، اما وجودش با ادعای README («zero plaintext password into dconf») در تضاد است و اگر نسخه‌ای از کد روزی آن را بنویسد، رمز به‌صورت متن خام در dconf می‌رود. حذفش کنید. |
| پایین | **دنبال‌کردن redirect بدون بازبینی scheme** در `utils.download_remote_to_destination` (urllib می‌تواند http→file را دنبال کند؛ فایل محلی خوانده شده و وارد حافظه می‌شود؛ تأثیر عملی کم است چون بعداً باید ZIP معتبر باشد، ولی بهتر است `HTTPRedirectHandler` سفارشی با محدودیت http/https اضافه شود). |
| پایین | **بدون محدودیت حجم دانلود ZIP** — یک URL مخرب می‌تواند حافظه/دیسک را پر کند (memory exhaustion). سقف حجم (مثلاً ۵۰MB) و بررسی نسبت فشرده‌سازی (zip bomb) پیشنهاد می‌شود. |
| نکته معماری | **رمز در keyring خود NetworkManager**: بک‌اند NM پروفایل را با `save_to_disk=TRUE` ذخیره می‌کند و چون `secret flags` تنظیم نشده، سرویس NM خودش رمز را در `/etc/NetworkManager/system-connections` (root-only) نگه می‌دارد. این اجتناب‌ناپذیر است ولی ادعای «هیچ متن خامی روی دیسک» را باید با این قید بیان کرد؛ بهتر است `nm_setting_vpn_set_secret_flags(...AGENT_OWNED...)` ست شود تا رمز فقط نزد secret agent بماند. |
| نکته طراحی | در بک‌اند OpenVPN3، کانفیگ (که می‌تواند کلید خصوصی inline داشته باشد) و رمز عبور از **system D-Bus** رد می‌شوند — این ذات معماری openvpn3 است، ولی خوب است در README به آن اشاره شود. |
| نکته | **`reset_paths()` قبل از دانلود** در `validate_and_load` دایرکتوری کانفیگ‌ها را پاک می‌کند (اگر بیش از ۱ فایل داشته باشد)؛ اگر دانلود ناموفق باشد، **کانفیگ‌های قبلی کاربر از دست می‌روند**. بهتر است دانلود در دایرکتوری موقت انجام و پس از موفقیت جایگزین شود. |

### پیکربندی شبکه‌ای ✅
- تست پینگ TCP چندنخی با ۱۲ worker و timeout هر اندپوینت ۱.۵ ثانیه — منطقی.
- مانیتورینگ `/proc/net/dev` فقط برای اینترفیس‌های tun/tap/ovpn/ppp/wg با fallback — درست.
- D-Bus listener ها unsubscribe می‌شوند (`remove_watch`/`unsubscribe_all`) — نشت سیگنال وجود ندارد.

---

## ۴. ارزیابی مستندات (Documentation)

### نقاط قوت ✅
- **README دوزبانه و کامل**: معرفی، تصاویر، جدول ویژگی‌ها، ۴ روش نصب (deb/Flatpak/meson/debug)، تست، اطلاعات تماس — از بیشتر پروژه‌های متن‌باز بهتر است.
- **PACKAGING.md واقعاً حرفه‌ای**: راهنمای گام‌به‌گام .deb، .rpm، Flatpak، PKGBUILD آرچ و CI — نادر و ارزشمند.
- **داک‌استرینگ دوزبانه در کل کد** — کیفیت مستندات درون‌کدی بالا.
- **ترجمه فارسی ۵۰ از ۵۱ رشته** (۹۸٪)، ایتالیایی و پرتغالی ~۹۵٪.
- فایل‌های metainfo (AppStream) با content-rating و releases، desktop file، gschema — کامل.

### مشکلات ⚠️
1. **«GitHub Releases» وجود ندارد!** README می‌گوید از Releases دانلود کنید، ولی مخزن **هیچ tag/release ای ندارد** (بررسی شد). باید tag v1.5.0 ساخته و بسته‌ها پیوست شوند.
2. **لینک اسکرین‌شات متادیتا خراب است**: metainfo به برنچ `1.5` اشاره می‌کند (`raw.githubusercontent.com/.../1.5/static/window.png`) که وجود ندارد (فقط master و برنچ‌های arena) — باید به `master` یا یک tag واقعی تغییر کند.
3. **CI فعال نیست**: فایل `dist/ci/ci-cd.yml` فقط یک قالب است و در `.github/workflows/` قرار نگرفته (فقط FUNDING.yml هست). ضمن اینکه FUNDING.yml هم فقط قالب خالی است.
4. **ناسازگاری‌های مستندات بسته‌بندی**:
   - PACKAGING.md می‌گوید `flatpak install ... org.gnome.Sdk//46` ولی manifest روی `runtime-version: '50'` است.
   - دستور `tar ... .` در PACKAGING.md آرشیوی بدون دایرکتوری ریشه می‌سازد ولی spec با `%autosetup -n eOVPN-Pro` انتظار دایرکتوری `eOVPN-Pro` دارد — بیلد rpm طبق همین دستورالعمل خطا می‌دهد.
   - `dist/flatpak/README.md` به فایل‌های `polkit-build-*.patch` اشاره می‌کند که در مخزن نیستند (قدیمی).
5. **`tests/README.md` دستور اشتباه دارد**: `python -m unittest tests` چیزی اجرا نمی‌کند؛ دستور درست `python3 -m unittest discover -s tests -v` است (که در README اصلی درست آمده).
6. غیبت `CONTRIBUTING.md`، `SECURITY.md` و معماری‌داک — برای پروژه‌ای در این سطح پیشنهاد می‌شود.

---

## ۵. امتیازدهی

| بخش | امتیاز از ۱۰ | جمع‌بندی |
|---|---|---|
| کیفیت کد و معماری | **7.0** | ماژولار و خواناتر از میانگین، با داک‌استرینگ و تایپ‌هینت؛ اما state سراسری، کلاس‌های حجیم و چند باگ منطقی (off-by-one، نخ‌ها، enums.h) |
| امنیت | **6.5** | پایه امنیتی قوی (Keyring، 0600، Zip-Slip، HTTPS)؛ اما لاگ OTP، حذف بی‌تأیید همه VPNها، کلید مرده auth-pass و چند مورد سطح پایین |
| مستندات | **7.0** | README و PACKAGING عالی و دوزبانه؛ اما بدون release واقعی، لینک متادیتای خراب، CI غیرفعال و چند ناسازگاری |
| قابلیت توسعه (Scalability) | **6.5** | تست پینگ موازی و انتزاع بک‌اند خوب؛ اما سرویس‌لوکیتور سراسری، تماس‌های sync در D-Bus و GMainLoop تودرتو در بایندینگ C، تک‌نشینی بودن وضعیت openvpn3 |
| **میانگین کل** | **6.8 / 10** | |

> جمع امتیازها: (7.0 + 6.5 + 7.0 + 6.5) ÷ 4 = **6.75 ≈ 6.8**

---

## ۶. آمادگی انتشار (.deb / .rpm / .AppImage / Flatpak)

### 📦 .deb — ✅ تقریباً آماده (۹۰٪)
زیرساخت کامل است: `debian/` (control، rules، postinst، postrm، changelog، copyright)، بیلد با `dh --buildsystem=meson`، وابستگی‌ها درست (python3-gi، gir1.2-*، network-manager-openvpn، openvpn)، اسکریپت‌های postinst برای schemas/icon cache. برای انتشار واقعی فقط:
1. رفع باگ‌های امنیتی/منطقی بالا (لاگ OTP، تأیید حذف VPNها، off-by-one)؛
2. ساخت tag و فعال‌سازی workflow در `.github/workflows/ci-cd.yml`؛
3. تست واقعی `dpkg-buildpackage -us -uc -b` روی اوبونتو ۲۴.۰۴.

### 📦 .rpm — ⚠️ نیازمند اصلاح و تست
spec کامل و حرفه‌ای است (BuildRequires/Requires درست، %check با desktop-file-validate) ولی:
1. ناسازگاری دستور tar در PACKAGING.md با `%autosetup -n eOVPN-Pro` (باید آرشیو حاوی دایرکتوری `eOVPN-Pro/` باشد)؛
2. `appstream-util` در فدورای جدید به `appstreamcli` تغییر نام داده؛
3. هنوز روی فدورا/اopenSUSE تست نشده (هیچ CI برای rpm نیست).

### 📦 .AppImage — ❌ آماده نیست (زیرساخت صفر)
هیچ فایلی برای AppImage وجود ندارد (نه linuxdeploy/AppImageTool، نه AppDir، نه اسکریپت ساخت). ساخت آن نیازمند: bundling پایتون + PyGObject + GTK/Libadwaita + `libeovpn_nm.so` و `_libeovpn_nm.so` در AppDir، و تنظیم `APPIMAGE` runtime. از آنجا که اپلیکیشن به NetworkManager سامانه (system D-Bus) وابسته است، AppImage عملاً فقط به‌عنوان «نسخه قابل‌حمل با نیاز به NM نصب‌شده» معنا دارد. با یک CI job + `linuxdeploy-plugin-gtk` قابل افزودن است، ولی امروز نه.

### 📦 Flatpak — ⚠️ نزدیک به آماده ولی پرریسک (۷۰٪)
manifest واقعاً جدی است: خودش NetworkManager 1.38، libnma، polkit، udev، libndp، openvpn3 v24.1 (با patch مناسب)، و python3-cffi را می‌سازد و finish-args محدود و درست دارد (system-talk-name فقط برای NM و سرویس‌های openvpn3). اما:
1. **runtime-version '50'** — باید با نسخه‌ای که واقعاً در flathub موجود است تطبیق داده شود (مستندات می‌گویند 46)؛
2. **بک‌اند OpenVPN3 درون Flatpak ریسک دارد**: `extract_enums.py` در زمان configure به ماژول پایتون `openvpn3` نیاز دارد و سرویس openvpn3 سندباکس‌شده باید بتواند روی system bus ثبت شود — این مسیر باید با یک بیلد واقعی flatpak-builder اثبات شود؛
3. سرویس‌های openvpn3 به host system bus نیاز دارند (بدون `--socket=system-bus` سرویس داخل سندباکس نمی‌تواند نام D-Bus بگیرد)؛
4. ساخت کامل (NM از سورس) زمان‌بر است ولی خودکار.

### جمع‌بندی انتشار
- **.deb**: بله، با رفع ۳-۴ مورد کوچک — همین هفته قابل انتشار است.
- **.rpm**: بله، پس از یک بار تست واقعی روی فدورا و اصلاح دستور tar.
- **Flatpak**: نزدیک، ولی یک بیلد آزمایشی کامل (ترجیحاً در CI) لازم است.
- **AppImage**: خیر — باید از صفر ساخته شود.

---

## 🎯 فهرست اقدامات پیشنهادی (اولویت‌بندی)

**P0 (امنیت/داده):**
1. حذف لاگ OTP از `backend/openvpn3/dbus.py` (و لاگ نکردن هیچ راز دیگری)
2. افزودن دیالوگ تأیید به «Delete All VPN Connections!» (یا محدود کردن به UUIDهای خود برنامه)
3. حذف کلید `auth-pass` از gschema؛ انتقال دانلود ZIP به دایرکتوری موقت (جلوگیری از ازدست‌رفتن کانفیگ‌ها هنگام خطای Update)

**P1 (باگ):**
4. رفع off-by-one در `LAST_CONNECTED_CURSOR`
5. رفع crash احتمالی `AUTH_USER=None` در `sub_attention_signal`
6. بازگردانی به‌روزرسانی ویجت‌ها به نخ اصلی با `GLib.idle_add` در `update_set_ip_flag`
7. اصلاح `extract_enums.py` به حالت write و تعیین وابستگی `openvpn3` پایتون در مستندات ساخت

**P2 (کیفیت/انتشار):**
8. تصحیح `Gtk.License.LGPL_3_0` → `GPL_3_0`
9. فعال‌سازی `dist/ci/ci-cd.yml` در `.github/workflows/` + اجرای flake8/mypy + ساخت rpm و flatpak در CI
10. ایجاد tag/release `v1.5.0` و اصلاح لینک اسکرین‌شات متادیتا به `master`
11. رفع ناسازگاری‌های PACKAGING.md (نسخه runtime، دستور tar، `appstreamcli`)
12. تکمیل FUNDING.yml یا حذف آن

---

*بررسی با نیت خیرخواهانه و برای ارتقای پروژه انجام شد. یا علی مدد 💚*
