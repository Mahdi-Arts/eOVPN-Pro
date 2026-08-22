# 🔍 تحلیل جامع و موشکافانه مخزن eOVPN-Pro — نسخه ۱.۵.۰

**تاریخ تحلیل:** 2026-08-22
**شاخه تحلیل‌شده:** `master` (کامیت `710d13d` — «Apply Review Action Plan»)
**دامنه:** کل کدبیس (Python + C/CFFI + Meson)، بسته‌بندی (.deb/.rpm/Flatpak)، CI/CD، مستندات، امنیت، تست‌ها (اجرای مجدد: **۳۵/۳۵ تست پاس ✅**)

> خلاصه اجرایی: پروژه در مقایسه با وضعیت قبل (امتیاز ۶.۸ در `docs/REVIEW.md`) به‌طور قابل‌توجهی ارتقا یافته: لاگ OTP حذف شده، Zip-Slip/zip-bomb محافظت می‌شود، دانلود مرحله‌ای (Staging) شده، تست‌ها از ۱۲ به ۳۵ رسیده و مستندات دوزبانه کامل شده‌اند.
> **مهم‌ترین شکاف باقی‌مانده:** فایل workflow در `dist/ci/ci-cd.yml` است و در `.github/workflows/` **وجود ندارد** → خط لوله CI در گیت‌هاب **فعال نیست**، با وجود اینکه README و QA_REPORT ادعای فعالیت آن را دارند. علاوه بر آن چند مورد امنیتی P0 (اجرای اسکریپت‌های داخل کانفیگ OpenVPN، ذخیره رمز توسط NetworkManager روی دیسک، دسترسی به ویجت GTK از نخ کارگر) و ریسک بیلد Flatpak باقی است.

---

## ۱. تحلیل معماری و ساختار (Architecture & Structure)

### نمای کلی

| جنبه | وضعیت |
|---|---|
| زبان / UI | Python 3.10+ + GTK4 + Libadwaita |
| سیستم ساخت | Meson + Ninja + CFFI (بایندینگ C برای libnm و D-Bus سرویس openvpn3) |
| بک‌اندها | NetworkManager (libnm از طریق C) و OpenVPN 3 Linux (D-Bus) — با انتزاع `ConnectionManager` (ABC) |
| محلی‌سازی | gettext — ۴ زبان: en (34)، fa (96)، it (31)، pt_BR (47) |
| تست | unittest — ۳۵ تست آفلاین (تأیید شد ✅) |
| مجوز | GPL-3.0-or-later (هدِر GPL روی هر دو فایل C ✅) |
| نسخه | منبع واحد در `meson.build` (1.5.0)؛ changelog و spec ها دستی هماهنگ‌شده |

### سازمان‌دهی فایل‌ها — نقاط قوت ✅

```
eovpn/
├── application.py          # نقطه ورود، آرگومان‌های CLI، i18n/RTL
├── eovpn_base.py           # کلاس پایه، GSettings، Keyring، اعلان‌ها، state store
├── main_window.py          # پنجره اصلی (1689 خط — حجیم)
├── settings_window.py      # پنجره تنظیمات (595 خط — حجیم)
├── connection_manager.py   # انتزاع + دو بک‌اند
├── speed_test.py           # تست پینگ TCP موازی (ThreadPool)
├── auto_connect.py         # موتور اتصال آبشاری (خالص و تست‌پذیر)
├── utils.py                # ZIP امن، دانلود، فیلتر سرور
├── ip_lookup/lookup.py     # استعلام IP/کشور با HTTPS و fallback سه‌گانه
├── dialogs/otp.py          # دیالوگ 2FA شش‌رقمی
└── backend/{networkmanager,openvpn3}/   # بایندینگ CFFI + شنونده‌های D-Bus
subprojects/                # کد C: eovpn_nm.c (450) و openvpn3.c (697)
data/                       # gresource (268 ورودی — همگی موجود ✅)، آیکون‌ها، UI، پرچم‌ها
debian/  dist/{flatpak,rpm,ci}  po/  tests/  docs/   # بسته‌بندی و مستندات
```

نقاط قوت معماری:
- **انتزاع درست بک‌اند** (`ConnectionManager` انتزاعی + دو پیاده‌سازی) — افزودن بک‌اند سوم ساده است.
- **تفکیک منطق از UI**: ماژول‌های `utils`، `speed_test`، `auto_connect`، `lookup` خالص و بدون وابستگی GTK هستند و به همین دلیل تست‌پذیرند (تست‌ها همگی آفلاین‌اند).
- **باندل gresource** برای UI/CSS/آیکون/پرچم — نصب تمیز.
- **امنیت در طراحی** (نه وصله‌کاری): Keyring، فایل موقت 0600، محافظت Zip-Slip، سقف حجم.
- داک‌استرینگ‌های دوزبانه فارسی/انگلیسی در تمام ماژول‌ها — کمیاب و ارزشمند.

### Anti-pattern ها ⚠️

1. **Service-Locator سراسری (Global Mutable State)**: دیکشنری‌های ماژولی `_storage_record`، `_builder_record`، `_session_secrets` + متدهای `Base.store/retrieve`. وضعیت پنهان، تست‌پذیری پایین، و با چند-پنجره/چند-نشستی شدن می‌شکند. (در `docs/ARCHITECTURE.md` به‌عنوان کار آینده مستند شده — منصفانه ✅)
2. **God Class**: `MainWindow.setup()` حدود ۱۰۰۰ خط از ۱۶۸۹ خط فایل را تشکیل می‌دهد (ساخت ویجت + اکشن‌ها + منو + میانبرها)؛ `SettingsWindow.setup()` هم ~۴۵۰ خط. نقض SRP.
3. **کد تکراری (DRY)**: دو پارسر مجزای `.ovpn` (`speed_test.parse_ovpn_remote` و `auto_connect.parse_ovpn_endpoints`)؛ متد `to_cffi_string` در هر دو کلاس بک‌اند تکرار شده؛ سه متد اعلان (`send_*_notification`) تقریباً یکسان‌اند؛ دو کلاس هم‌نام `Signals` در `main_window.py` و `settings_window.py`.
4. **GMainLoop تودرتو روی نخ اصلی GTK** در `eovpn_nm.c`: همه‌ی `add_connection`/`activate_connection`/`disconnect`/`delete_connection` یک `GMainLoop` جدید اجرا می‌کنند و از نخ UI صدا زده می‌شوند → **فریز UI + بازورودی (reentrancy) + بدون تایم‌اوت** (در صورت پاسخ‌ندادن D-Bus، برنامه بی‌نهایت قفل می‌ماند).
5. **Stateful سراسری در C**: `static GDBusProxy *UniqueSession` در `openvpn3.c` — نه thread-safe، تک‌نشینی اجباری.
6. **فایل‌های spec تکراری**: `eovpn-pro.spec` (ریشه) و `dist/rpm/eovpn-pro.spec` — تقریباً یکسان ولی با اختلاف (کامنت، `%global __name`، newline)؛ ریسک واگرایی نسخه.
7. **CI «جا به جا»**: workflow فقط در `dist/ci/ci-cd.yml` است — نه در `.github/workflows/`؛ README و PACKAGING و QA_REPORT همگی به مسیرهای ناموجود ارجاع می‌دهند (شکاف مستندات-واقعیت).
8. **`otp.blp` + `otp.ui` تولیدی هر دو کامیت شده** ولی `blueprint-compiler` در بیلد نیست → ریسک کهنه‌شدن .ui.
9. **وراثت دوگانه شکننده**: `class MainWindow(Base, Gtk.Builder)` + `Gtk.Builder.__init__(self)` صریح — MRO غیرمتعارف.
10. **سانتینل رشته `"null"`** در `get_setting` — اگر کاربر واقعاً مقدار `"null"` ذخیره کند، `None` برمی‌گردد (برخورد مقدار).
11. **هک `sys.argv.remove("-c"/"--config")`** در `application.py` — دستکاری خام آرگومان‌ها.
12. **ایمپورت‌های ناهمگون**: `otp.py` و `backend/openvpn3/dbus.py` از ایمپورت مطلق (`from eovpn.eovpn_base import`) استفاده می‌کنند؛ بقیه نسبی.
13. **بازتعریف closure در هر تیک**: `format_speed`/`format_size` داخل `update_network_speed` هر ثانیه ساخته می‌شوند.
14. **حالت آبشاری پخش‌شده روی ~۱۵ attribute** (`_cascade_*`) — یک state machine که شایسته کلاس مجزاست.

---

## ۲. بررسی کیفیت کد (Code Quality & Maintainability)

### نقاط قوت ✅

- داک‌استرینگ دوزبانه کامل + تایپ‌هینت مدرن (`str | None`، `dict[str, float]`، `frozenset[str]`) در سراسر کد.
- مدیریت خطای منسجم: تقریباً تمام مسیرهای I/O و D-Bus در try/except با لاگ‌گذاری سطح‌بندی‌شده.
- **۳۵ تست واحد معنادار، همه پاس** (اجرای مجدد توسط تحلیلگر ✅): Zip-Slip، zip-bomb، پاک‌سازی پروتکل، تایم‌اوت تطبیقی، صف آبشاری، فیلتر سرور، Lookup با mock.
- ابزارهای کیفیت کد: `.flake8`، `pyproject.toml` (ruff + mypy با تنظیمات دقیق)، `.editorconfig`، `.clang-format` (GNU).
- کد C تمیز: بررسی `GError` در اکثر نقاط، مدیریت حافظه با `g_free`/`g_object_unref`.
- تست‌های واحد ماژول‌های خالص جدا از GTK — معماری تست‌پذیر.
- نام‌گذاری عمدتاً گویا (`compute_attempt_timeout`، `build_cascade_queue`، `matches_server_filter`).

### مشکلات ⚠️

| شدت | مورد | محل |
|---|---|---|
| متوسط | پیچیدگی شناختی بالا در `setup()`ها و `on_connection_event` (شاخه‌های عمیق، تو در تو) | `main_window.py`، `settings_window.py` |
| متوسط | state آبشاری پخش‌شده روی دوجین attribute — خطای انسانی را بالا می‌برد | `main_window.py` |
| متوسط | پارامترهای طولانی: `on_reset_btn_clicked(button, entries, buttons, switches, window)` | `settings_window.py` |
| پایین | `list_filter_match` در هر ردیف `self.get_favorites()` می‌خواند (دسترسی GSettings به‌ازای هر ردیف در هر فیلتر) | `main_window.py` |
| پایین | `load_only` کل ListStore را از نو می‌سازد — بازسازی O(n) کل لیست | `eovpn_base.py` |
| پایین | تست‌ها فایل‌هایی در CWD می‌سازند (`test_config.ovpn`) به‌جای tempfile | `tests/test_speed_test.py` |
| پایین | کد مرده: `undo_reset_settings` (هیچ استفاده‌ای)، `NMDbus.remove_watch` (بدون caller) | `eovpn_base.py`، `backend/networkmanager/dbus.py` |
| پایین | `self.CM = lambda: ...` — attribute تابعی عجیب؛ بهتر است متد واقعی | `main_window.py` |
| پایین | نام‌گذاری: `OTpMainWindow`، `self.psh`، `StorageItem.CONFIGS_LIST = "listbox-rows-index"` (نام گمراه‌کننده) | `otp.ui`، `main_window.py`، `eovpn_base.py` |
| پایین | `update_network_speed`: fallback «rx==0 و tx==0» حالت «ترافیک صفر واقعی» را از «بدون اینترفیس VPN» تشخیص نمی‌دهد | `main_window.py` |
| پایین | `subprocess.run(["xdg-open", ...])` به‌صورت blocking — باید `Popen` باشد | `eovpn_base.py` |

**ارزیابی اصول:** Clean Code (تا حدی — خوانایی خوب، ولی کلاس‌های حجیم)، SOLID (OCP ✅ با انتزاع بک‌اند؛ SRP ❌ در God Class ها؛ DIP ⚠️ به‌خاطر Service Locator)، DRY (⚠️ — موارد تکراری بالا)، KISS (⚠️ — state آبشاری و سانتینل «null» پیچیدگی غیرضروری دارند).

---

## ۳. بررسی امنیت و شبکه (Security & Network)

### نقاط قوت — طراحی امنیتی واقعی ✅

- **رمز عبور**: Secret Service (Keyring) با Schema اختصاصی + fallback فقط در RAM پروسه (`_session_secrets`)؛ هیچ‌جا در dconf/فایل نوشته نمی‌شود. اسکن کامل مخزن: **هیچ کلید/توکن/رمز جاسازی‌شده‌ای یافت نشد** ✅
- **فایل موقت امن**: `NamedTemporaryFile` + `chmod 0o600` + حذف در `finally` (ضد race condition).
- **ZIP**: محافظت Zip-Slip (flatten + `realpath` + `commonpath` + تست اختصاصی)، سقف دانلود ۶۴MiB، سقف استخراج ۲۵۶MiB (zip-bomb)، ریدایرکت فقط http/https (`_SafeRedirectHandler`).
- **استعلام IP فقط HTTPS** با سه ارائه‌دهنده جایگزین و timeout.
- OTP **هرگز لاگ نمی‌شود** (تأیید شد: `send_otp` فقط گروه چالش را لاگ می‌کند ✅).
- «Delete All VPN Connections» اکنون دیالوگ تأیید صریح دارد ✅.
- هیچ `shell=True`/`eval`/`os.system` در کل کدبیس نیست؛ subprocess فقط با لیست آرگومان ✅.
- دانلود مرحله‌ای (staging + swap اتمی) — کانفیگ‌های قبلی هنگام خطای Update از بین نمی‌روند ✅.
- `.gitignore` از کامیت شدن `*.ovpn`/`*.crt`/`*.key` جلوگیری می‌کند ✅.

### آسیب‌پذیری‌ها و ریسک‌ها ⚠️

| شدت | مورد | جزئیات / راه‌حل |
|---|---|---|
| **بالا** | **اجرای کد از کانفیگ‌های نامعتبر OpenVPN** | فایل `.ovpn` می‌تواند شامل دایرکتیوهای `up`/`down`/`route-up`/`ipchange`/`script-security` باشد که openvpn آن‌ها را (اغلب با اختیارات بالا) اجرا می‌کند. دانلود از URL دلخواه + ایمپورت خودکار = عملاً «دانلود و اجرا». راه‌حل: اسکن دایرکتیوهای خطرناک هنگام ایمپورت + هشدار به کاربر، اجرای openvpn با user/group غیرprivileged، و پین کردن checksum منبع. |
| **متوسط** | **ذخیره رمز توسط NetworkManager روی دیسک** | در `eovpn_nm.c`، `nm_setting_vpn_add_secret` + `add_connection(..., save_to_disk=TRUE)` بدون تنظیم secret flags → NM رمز را در `/etc/NetworkManager/system-connections` (root-only ولی **روی دیسک**) نگه می‌دارد — با ادعای «zero plaintext on disk» در README/SECURITY.md در تضاد است. راه‌حل: `NM_SETTING_SECRET_FLAG_AGENT_OWNED` تا رمز فقط نزد secret agent بماند. |
| **متوسط** | **دسترسی به ویجت GTK از نخ کارگر** | در `eovpn_base.validate_and_load`، تابع `dispatch()` (نخ کارگر) `ca_button.set_label(...)` را صدا می‌زند و `set_setting` اجرا می‌کند. GTK نخ‌امن است → crash احتمالی. (مسیر IP lookup قبلاً با `GLib.idle_add` درست شده ولی این مسیر نه.) |
| **متوسط** | **تماس‌های D-Bus بدون تایم‌اوت + GMainLoop بی‌وچ‌داگ** | در `openvpn3.c` همه‌ی `g_dbus_proxy_call_sync(..., -1, ...)` و در `eovpn_nm.c` حلقه‌های `g_main_loop_run` بدون محدودیت زمان — اگر سرویس D-Bus پاسخ ندهد، برنامه بی‌نهایت قفل می‌ماند (availability DoS). |
| متوسط | **ایمپورت پوشه محلی بدون سقف حجم** | فقط ZIP سقف دارد؛ کپی از یک پوشه محلی بزرگ می‌تواند دیسک را پر کند. |
| متوسط | **HTTP (غیر HTTPS) برای دانلود کانفیگ مجاز است** | ریسک دستکاری کانفیگ در مسیر (که به ریسک «اجرای کد» بالا می‌پیوندد). پیشنهاد: گزینه https-only. |
| پایین-متوسط | **Flatpak: patch غیرفعال‌سازی بررسی مالکیت پلاگین NM** | `0001-disable-ownership-check-for-plugins.patch` لازمه سندباکس است ولی یک کنترل امنیتی NM را دور می‌زند؛ باید مستند و محدود بماند. |
| پایین | **کلیدهای Keyring یتیم** | تغییر username، ورودی قدیمی Keyring را پاک نمی‌کند (`settings_window.process_password`). |
| پایین | **بدون اسکن CVE وابستگی‌ها** | وابستگی‌ها loose هستند (`cffi>=1.15`، `PyGObject>=3.42`) و هیچ `pip-audit`/dependabot/CodeQL در CI نیست. پین‌های subprojects (NM 1.38.2، openvpn3 v24.1، polkit 122، protobuf v34.1) بدون اسکن خودکار امنیتی‌اند. |
| پایین | **لاگ مسیرهای D-Bus** | `logger.info("OpenVPN 3 Config Path: %s", ...)` — خود مسیر راز نیست، ولی الگوی «لاگ نکردن metadata حساس» باید در کل رعایت شود. |

### امنیت لایه شبکه ✅

- تست پینگ TCP چندنخی (۱۲ worker، timeout هر اندپوینت ۱.۵s) — منطقی.
- مانیتورینگ `/proc/net/dev` فقط برای tun/tap/ovpn/ppp/wg.
- D-Bus listener ها با `unsubscribe_all` پاک می‌شوند.
- Flatpak `finish-args` محدود و اصولی است (`--system-talk-name` فقط برای NM و سرویس‌های openvpn3).

### نقشه OWASP (برای دسکتاپ‌اپ)

| OWASP | وضعیت |
|---|---|
| A01 Broken Access Control | ✅ مدل محلی و بدون سطح دسترسی مشترک |
| A02 Cryptographic Failures | ✅ Keyring + HTTPS؛ ⚠️ رمز NM روی دیسک |
| A03 Injection | ✅ بدون shell؛ ⚠️ دایرکتیوهای اسکریپت OpenVPN |
| A06 Vulnerable Components | ⚠️ بدون pip-audit/dependabot |
| A08 Integrity Failures | ⚠️ دانلود بدون checksum/signature |
| A09 Logging Failures | ✅ OTP حذف شد؛ ✅ لاگ‌ها سطح‌بندی‌شده |

---

## ۴. ارزیابی مستندات (Documentation)

### نقاط قوت ✅

- **README دوزبانه کامل**: معرفی، ۴ روش نصب، دستورات تست/لینت، جدول مستندات، اطلاعات تماس.
- **PACKAGING.md حرفه‌ای**: راهنمای گام‌به‌گام .deb/.rpm/Flatpak/Arch + بخش صادقانه AppImage (اعلام «آماده نیست» ✅).
- **`docs/ARCHITECTURE.md`** (لایه‌ها، تصمیم‌ها، نقشه ماژول‌ها)، **`docs/RELEASE_CHECKLIST.md`** (ران‌بوک کامل انتشار)، **`SECURITY.md`**، **`CONTRIBUTING.md`** — همه دوزبانه.
- داک‌استرینگ دوزبانه در ۱۰۰٪ ماژول‌ها + docstring برای توابع خالص با `:param:`.
- `metainfo.xml` با releases، content-rating، kudos، screenshots (لینک به `master` — اکنون درست است ✅).
- `debian/changelog` و `debian/copyright` درست.

### مشکلات ⚠️

1. **CI غیرفعال ولی ادعاشده**: README نشان CI به `.github/workflows/ci-cd.yml` اشاره می‌کند که **وجود ندارد**؛ PACKAGING.md §5 ادعای «دو workflow فعال» (از جمله `.github/workflows/release.yml`) دارد که **هیچ‌کدام وجود ندارند**؛ QA_REPORT.md هم ادعای فعال‌سازی CI در `.github/workflows/` می‌کند. واقعیت: فقط `dist/ci/ci-cd.yml` هست.
2. `SECURITY.md` ادعای «never disk» را بدون قید NM بیان می‌کند (نگاه کنید به بند ۳).
3. فایل استاب `REVIEW.md` در ریشه + نسخه کامل در `docs/REVIEW.md` — بهتر است استاب حذف و لینک در README اصلاح شود.
4. عدم وجود `CHANGELOG.md` مستقل (changelog فقط در debian و metainfo) — جزئی.
5. عدم وجود man page (`eovpn.1`) — جزئی.
6. `data/ui/README.md` و `data/icons/README.md` تقریباً خالی‌اند.
7. مستندات معماری موتور آبشاری (cascade) و قرارداد «null» سنتینل مستند نشده.

---

## ۵. ارزیابی انتشار و بسته‌بندی (Packaging Readiness)

### 📦 .deb — ✅ تقریباً آماده (~۹۰٪)
زیرساخت کامل: `debian/` (control با Build-Depends و Depends درست، rules با `dh --buildsystem=meson` و `-Dopenvpn3=false`، postinst/postrm برای schemas/icon cache/desktop-database، changelog، copyright). برای انتشار واقعی: فعال‌سازی CI + یک بیلد واقعی `dpkg-buildpackage` + ساخت tag.

### 📦 .rpm — ⚠️ نیازمند تست (۷۰٪)
spec کامل و حرفه‌ای است ولی:
1. **تکراری است**: `eovpn-pro.spec` (ریشه) + `dist/rpm/eovpn-pro.spec` — یکی باید حذف شود.
2. هیچ جاب CI برای rpm نیست (باید روی Fedora واقعاً تست شود).
3. `%check` از `appstreamcli validate ... || true` استفاده می‌کند — «true» ضعف را می‌پوشاند.
4. دستور ساخت آرشیو (`git archive --prefix=eovpn-pro-1.5.0/`) باید با `%autosetup` هماهنگ باشد (در PACKAGING.md اصلاح شده ✅ ولی تست نشده).

### 📦 Flatpak — ⚠️ پرریسک و تست‌نشده (۶۰٪)
مانیفست جدی است (ساخت NM 1.38.2، libnma، polkit، udev، libndp، openvpn3 v24.1 + patch، python3-cffi) ولی:
1. **هرگز بیلد نشده** — هیچ جاب CI فعالی نیست.
2. **ریسک معماری**: برنامه با `Gio.bus_get_sync(SYSTEM)` به system bus **میزبان** وصل می‌شود؛ NM سندباکس‌شده برای ثبت نام D-Bus خود به system bus نیاز دارد — `--system-talk-name` فقط «گفتگو» می‌دهد نه «ثبت نام» → احتمالاً باید `--socket=system-bus` یا راه‌اندازی باس خصوصی + wrapper تصمیم‌گیری شود.
3. `extract_enums.py` در زمان configure به بایندینگ پایتون `openvpn3` نیاز دارد — در مانیفست باید ماژول پایتون `openvpn3` (یا `-Dopenvpn3=false`) تأمین شود.
4. `runtime-version: '50'` باید با نسخه‌ای که واقعاً روی Flathub موجود است تطبیق یابد.
5. polkit 122 در مانیفست — بهتر است به نسخه جدیدتر ارتقا یابد (اسکن CVE).

### 📦 .AppImage — ❌ آماده نیست (صادقانه در PACKAGING.md اعلام شده ✅)
نیازمند AppDir + linuxdeploy-plugin-gtk + باندل Python/PyGObject/CFFI/GTK؛ و چون به NM سامانه وابسته است، فقط «نسخه قابل‌حمل با NM نصب‌شده» معنا دارد. بدون CI job.

### CI/CD — ❌ بزرگ‌ترین بلوکر
- workflow فقط در `dist/ci/ci-cd.yml`؛ **در `.github/workflows/` نیست** → روی گیت‌هاب اجرا نمی‌شود.
- نشان (badge) README خراب است؛ PACKAGING/QA_REPORT خلاف واقع می‌گویند.
- جاب‌های موجود خوب طراحی شده‌اند (test → build-deb → build-flatpak → release) ولی ناقص: بدون mypy/ruff (با وجود نصب flake8)، بدون rpm، بدون AppImage، بدون dependabot/CodeQL/pip-audit، و job ریلیز فقط .deb را پیوست می‌کند (فلت‌پک نه).
- `.github/` فقط شامل `FUNDING.yml` (با جای‌نگهدارهای کامنت‌شده) است؛ قالب issue/PR نداریم.

---

## ۶. امتیازدهی کمی (Scoring)

| بخش | امتیاز | جمع‌بندی |
|---|---|---|
| کیفیت کد و معماری | **8.0/10** | ارتقای محسوس از 7.0: flake8 تمیز، ۳۵ تست، ماژول‌های خالص؛ ولی God Class ها، Service Locator، GMainLoop تودرتو و تکرار کد باقی‌اند |
| امنیت | **8.0/10** | از 6.5 به اینجا رسیده: همه P0های قبلی رفع شده (لاگ OTP، تأیید حذف، staging، Zip-Slip/بمب)؛ باقی: ریسک اجرای اسکریپت کانفیگ (بالا)، secret flags در NM، نخ‌امنی GTK در validate_and_load، تایم‌اوت D-Bus، نبود اسکن CVE |
| مستندات | **8.5/10** | دوزبانه و کامل‌تر از اکثر پروژه‌ها؛ ولی ادعاهای CI خلاف واقع، قید نشدن ذخیره رمز NM، نبود CHANGELOG/man page |
| قابلیت توسعه (Scalability) | **7.0/10** | تست موازی و انتزاع بک‌اند خوب؛ ولی تماس‌های sync D-Bus، حلقه‌های تودرتو، state سراسری، بازسازی کامل لیست، UniqueSession استاتیک |
| آمادگی بسته‌بندی (Packaging) | **7.5/10** | .deb ~آماده، .rpm نیازمند تست، Flatpak پرریسک و بیلد‌نشده، AppImage صفر، و CI غیرفعال که همه‌چیز را بلوک می‌کند |
| **میانگین** | **7.8/10** | (8.0 + 8.0 + 8.5 + 7.0 + 7.5) ÷ 5 = 7.8 |

> تفاوت با امتیاز ۸.۹ ادعاشده در QA_REPORT: آن گزارش فرض کرده CI فعال است و همه موارد P2 انجام شده‌اند؛ تحلیل مستقل نشان می‌دهد workflow هنوز در `.github/workflows/` نیست و چند مورد امنیتی/معماری باقی است.

---

## ۷. طرح اجرایی (Action Plan for Prompt 2)

فهرست شماره‌گذاری‌شده، دقیق و با مسیر فایل‌ها — آماده برای اجرا در مرحله بعد. اولویت‌بندی: **P0** (باید) ← **P1** (باید در این مرحله) ← **P2** (می‌تواند).

### P0 — امنیت (فایل‌هایی که باید ویرایش شوند)

1. **`subprojects/networkmanager/eovpn_nm.c`**: بعد از `nm_setting_vpn_add_secret(...)`، فراخوانی `nm_setting_set_secret_flags(vpn_settings, NM_SETTING_VPN_SECRET_PASSWORD, NM_SETTING_SECRET_FLAG_AGENT_OWNED, &err)` را اضافه کنید تا NM رمز را روی دیسک ذخیره نکند. سپس `SECURITY.md` را با این قید به‌روز کنید (بند «Dependency Responsibility»).
2. **`eovpn/utils.py`** — افزودن تابع خالص `audit_ovpn_content(file_path) -> list[str]` که دایرکتیوهای خطرناک (`up`، `down`، `route-up`، `ipchange`، `script-security`، `auth-user-pass` با مسیر فایل) را در کانفیگ‌های ایمپورت‌شده پیدا کند؛ و اعمال سقف حجم برای ایمپورت پوشه محلی (مثل `MAX_ZIP_DOWNLOAD_BYTES`). + تست در `tests/test_utils.py`.
3. **`eovpn/eovpn_base.py`** — در `validate_and_load`، انتقال `ca_button.set_label(...)` و `set_setting(...)` به داخل `GLib.idle_add` (نخ اصلی GTK)؛ اصلاح دسترسی به ویجت از نخ کارگر. (الگوی `_apply_ip_lookup` در `main_window.py` را الگو قرار دهید.)
4. **`subprojects/networkmanager/eovpn_nm.c` و `subprojects/openvpn3/openvpn3.c`** — افزودن تایم‌اوت: `g_timeout_add(15000, watchdog, loop)` + `g_main_loop_quit` در `eovpn_nm.c`، و جایگزینی `-1` با `15000` (ms) در همه‌ی `g_dbus_proxy_call_sync` های `openvpn3.c`؛ بازگرداندن پیام خطا به پایتون.
5. **`eovpn/backend/networkmanager/dbus.py` + `eovpn/main_window.py`** — اتصال `remove_watch()` به رویداد بسته‌شدن پنجره (فعلاً dead code است) تا اشتراک D-Bus پس از خروج پاک شود.
6. **`.github/workflows/ci-cd.yml` (جدید)** — اسکن امنیتی: استپ `pip-audit` + (اختیاری) `CodeQL` برای پایتون و C.

### P0 — CI/CD (فایل‌هایی که باید ساخته شوند — بلوکر اصلی)

7. **ساخت `.github/workflows/ci-cd.yml`**: کپی از `dist/ci/ci-cd.yml` + اصلاحات زیر؛ سپس **حذف `dist/ci/ci-cd.yml`** (منبع واحد).
   - افزودن استپ‌های `python3 -m mypy --ignore-missing-imports eovpn tests` و `python3 -m ruff check .` (هر دو در requirements-dev.txt هستند ولی در CI اجرا نمی‌شوند).
   - افزودن job `build-rpm` روی `fedora:latest` container با `rpmbuild -ba dist/rpm/eovpn-pro.spec`.
   - در job `release`: پیوست کردن `.flatpak` هم به GitHub Release (فعلاً فقط .deb).
   - افزودن `permissions: contents: write` در سطح workflow (به‌جای فقط job).
8. **ساخت `.github/dependabot.yml`**: اکوسیستم‌های `github-actions` و `pip`، هفتگی.
9. **اصلاح `README.md`** (نشان CI به مسیر واقعی) و **اصلاح `PACKAGING.md` §5** (حذف ادعای `release.yml` یا ساخت آن — پیشنهاد: حذف ادعا و ارجاع به `ci-cd.yml` واقعی).

### P1 — کیفیت کد و معماری

10. **یک‌پارچه‌سازی پارسر `.ovpn`** (DRY): `eovpn/auto_connect.py` — ارتقای `parse_ovpn_endpoints` به منبع واحد؛ `eovpn/speed_test.py` — حذف `parse_ovpn_remote` و استفاده از پارسر واحد؛ به‌روزرسانی `tests/test_auto_connect.py` و `tests/test_speed_test.py`.
11. **استخراج `to_cffi_string`** به یک کلاس/میکسین مشترک (مثلاً `eovpn/backend/_base.py` جدید) و حذف تکرار از `connection_manager.py`.
12. **شکستن `MainWindow.setup()`** در `eovpn/main_window.py` به متدهای `_build_pro_toolbar()`، `_build_filter_bar()`، `_build_cascade_banner()`، `_build_traffic_card()`، `_build_actions()`، `_build_menu()` — بدون تغییر رفتار.
13. **شکستن `SettingsWindow.setup()`** در `eovpn/settings_window.py` به `_build_setup_tab()`، `_build_general_tab()`، `_build_backend_tab()`، `_wire_signals()`.
14. **استخراج `CascadeEngine`**: فایل جدید `eovpn/cascade.py` (کلاس خالص و تست‌پذیر شامل queue/timeout/phase/failures) و سبک‌سازی `main_window.py`؛ تست‌های جدید در `tests/test_cascade.py`.
15. **حذف spec تکراری**: حذف `eovpn-pro.spec` (ریشه)، نگه‌داشتن `dist/rpm/eovpn-pro.spec` به‌عنوان منبع واحد؛ اصلاح ارجاع‌ها در `docs/RELEASE_CHECKLIST.md` و `PACKAGING.md`.
16. **یکسان‌سازی ایمپورت‌ها**: `eovpn/dialogs/otp.py` و `eovpn/backend/openvpn3/dbus.py` → ایمپورت نسبی (`from ..eovpn_base import ...`).
17. **حذف کد مرده**: `undo_reset_settings` (در `eovpn/eovpn_base.py`)؛ و `NMDbus.remove_watch` یا اتصال آن (بند ۵).
18. **بهداشت تست**: `tests/test_speed_test.py` — استفاده از `tempfile.TemporaryDirectory()` به‌جای فایل در CWD.
19. **`eovpn/main_window.py`** — انتقال `format_speed`/`format_size` به سطح ماژول (یا `utils.py`) و رفع ابهام fallback در `update_network_speed`.
20. **`eovpn/application.py`** — جایگزینی `sys.argv.remove` با پیمایش امن که فقط توکن‌های مستقل `-c`/`--config` را حذف کند.
21. **`eovpn/eovpn_base.py`** — جایگزینی سانتینل `"null"` با بررسی `len(val) == 0` (یا `GLib.Variant` خالی) و به‌روزرسانی gschema؛ هم‌زمان هماهنگی `Settings.all_settings` با gschema (تست خودکار: اسکریپت کوچک `scripts/check_schema_sync.py` یا استپ CI).
22. **`data/ui/otp.ui` + `eovpn/dialogs/otp.py`** — تغییر نام `OTpMainWindow` → `OTPMainWindow`؛ و حذف `data/ui/otp.blp` یا افزودن `blueprint-compiler` به بیلد (پیشنهاد: حذف .blp چون .ui منبع واقعی است).
23. **اتصال تست‌ها به Meson**: در `meson.build` افزودن `test('unit', python_installation, args: ['-m', 'unittest', 'discover', '-s', 'tests'])` تا `meson test` هم کار کند.
24. **`eovpn/eovpn_base.py`** — تغییر `subprocess.run(["xdg-open", ...])` به `subprocess.Popen` (غیرمسدودکننده).

### P2 — بسته‌بندی و انتشار

25. **Flatpak — تصمیم معماری system bus** (`dist/flatpak/com.github.mahdi-arts.eovpn-pro.yml` + `dist/flatpak/README.md`): بررسی و اصلاح نحوه اتصال NM سندباکس‌شده به system bus (افزودن `--socket=system-bus` به‌همراه policy یا wrapper با `DBUS_SYSTEM_BUS_ADDRESS` خصوصی)؛ ارتقای polkit به نسخه پایدار جدید؛ تأمین ماژول پایتون `openvpn3` برای `extract_enums.py` یا ساخت با `-Dopenvpn3=false` در فلت‌پک؛ تأیید `runtime-version` روی Flathub.
26. **AppImage** (اختیاری/تجربی): ساخت `dist/appimage/` با `linuxdeploy` + `linuxdeploy-plugin-gtk` + فایل `eovpn.AppDir` + job CI جدید؛ مستندسازی صادقانه وابستگی به NM میزبان (ادامه رویه فعلی PACKAGING.md).
27. **ساخت `eovpn.1`** (man page) + افزودن به `meson.build` و `debian/control`/spec.
28. **ساخت `CHANGELOG.md`** از `debian/changelog` و releases متادیتا.
29. **ساخت `.github/ISSUE_TEMPLATE/`** (bug_report.yml + feature_request.yml + config.yml با ارجاع SECURITY.md) و کامل‌کردن `FUNDING.yml`.
30. **ساخت `scripts/check_versions.py`**: بررسی هماهنگی نسخه بین `meson.build`، `debian/changelog`، `dist/rpm/eovpn-pro.spec`، `metainfo.xml` و اجرا در CI.
31. **به‌روزرسانی `QA_REPORT.md`** با بخش «تحلیل دوم» که وضعیت واقعی (CI غیرفعال، موارد P0 باقی‌مانده) را ثبت کند؛ و حذف استاب `REVIEW.md` ریشه.
32. **انتشار v1.5.0**: پس از سبز شدن CI، طبق `docs/RELEASE_CHECKLIST.md` تگ بزنید تا job های release و flatpak اجرا شوند.

### تغییرات معماری پیشنهادی (استراتژیک)

33. **جایگزینی تدریجی Service Locator** (`Base.store/retrieve`) با تزریق وابستگی ساده (مثلاً یک شیء `AppContext` که در `__init__` به کلاس‌ها پاس داده می‌شود) — بدون بازنویسی یک‌جا (ریسک رگرسیون).
34. **جدا کردن ساخت UI به فایل‌های `.ui`/`.blp`**: ویجت‌های ساخته‌شده در کد (toolbar، filter bar، traffic card) به Blueprint منتقل شوند تا `setup()`ها کوچک شوند (زیرساخت `blueprint-compiler` به بیلد اضافه شود).
35. **حالت چند-نشستی OpenVPN 3**: حذف `UniqueSession` استاتیک از `openvpn3.c` و نگه‌داشتن session در شیء پایتون (قابل چند نشست و thread-safe).

---

*این تحلیل مبنای فاز اجرایی بعدی است. یا علی مدد 💚*
