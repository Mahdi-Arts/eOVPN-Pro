# 🔍 بازبینی فنی سطح Senior (دور دوم) — مخزن eOVPN-Pro

**تاریخ بازبینی:** 2026-08-22 · **شاخه:** `arena/01a0290e-eovpn-pro` (کامیت پایه `f2c2df9` از `master`)
**نسخه:** 1.5.0 · **مجوز:** GPL-3.0-or-later · **App ID:** `com.github.mahdi-arts.eovpn-pro`
**نقش بازبین:** مهندس Full-Stack ارشد + مدیر سیستم لینوکس ارشد + متخصص امنیت سایبری + معمار نرم‌افزار
**روش:** خواندن کامل کدبیس (Python + C + Meson + پکیجینگ)، اجرای واقعی تست‌ها و اسکریپت‌های اعتبارسنجی، بازرسی GitHub از طریق API (`gh`)

> این گزارش، بازبینی مستقل دوم (`R2`) است؛ گزارش دور اول در `docs/REVIEW_SENIOR_2026-08.md` موجود است.
> وضعیت موارد همان دور مجدداً راستی‌آزمایی شده و یافته‌های جدید نیز اضافه شده‌اند.

---

## 🧪 راستی‌آزمایی‌های اجراشده (Evidences)

| بررسی | نتیجه |
|---|---|
| `python3 -m unittest discover -s tests -v` | ✅ **56/56 OK** (0.016s) |
| `python3 scripts/check_project_meta.py` | ✅ `All metadata checks passed (version 1.5.0)` |
| `python3 -m compileall eovpn tests` | ✅ بدون خطا |
| `gh api …/contents/.github/workflows` | ❌ **404 — پوشه وجود ندارد** |
| `gh api …/releases` | ❌ **هیچ Release منتشرشده‌ای وجود ندارد** |
| `gh api …/actions/runs` | ⚠️ فقط اجراهای داخلی Dependabot («Graph Update: pip») — بدون CI/Release |
| حجم کد | Python ≈ 6,221 خط · C ≈ 1,291 خط · UI برنامه‌ای (main.ui فقط ۱۷ خط) |

---

## ۱. تحلیل معماری و ساختار (Architecture & Structure)

### ۱.۱ نمای کلی و سازماندهی فایل‌ها

| لایه | فایل‌ها | مسئولیت |
|---|---|---|
| UI (GTK4 + Libadwaita) | `application.py`, `main_window.py` (۱٬۷۹۷ خط), `settings_window.py` (۷۵۱ خط), `dialogs/otp.py` | پنجره‌ها، اکشن‌ها، RTL/i18n |
| دامنه (Domain) | `connection_manager.py`, `eovpn_base.py`, `utils.py`, `speed_test.py`, `auto_connect.py`, `cascade.py`, `ip_lookup/` | منطق خالص، تنظیمات، ایمپورت امن، تست سرعت |
| بومی (Native) | `subprojects/networkmanager/eovpn_nm.c`, `subprojects/openvpn3/openvpn3.c` | libnm و openvpn3 D-Bus از طریق CFFI |
| داده/UI | `data/` (gresource: ۲۵۶ پرچم، CSS، ui) · `po/` (en, fa, it, pt_BR) | منابع باندل‌شده، ترجمه |
| پکیجینگ | `debian/`, `dist/{rpm,arch,appimage,flatpak}/`, `scripts/` | ۵ قالب بسته |
| مستندات | `README.md`, `docs/`, `SECURITY.md`, `PACKAGING.md`, `CHANGELOG.md`, `CONTRIBUTING.md` | دوزبانه و جامع |

### ۱.۲ نقاط قوت معماری ✅

1. **لایه‌بندی واضح UI / Domain / Native** و جداسازی منطق خالص از GTK — دلیل اصلی سبز بودن ۵۶ تست آفلاین؛ بهترین تصمیم معماری پروژه.
2. **انتزاع بک‌اند درست:** `ConnectionManager(ABC)` + دو پیاده‌سازی (`NetworkManager`, `OpenVPN3`) + fallback امن در `create_connection_manager()`؛ افزودن بک‌اند سوم (مثلاً WireGuard) کم‌هزینه است.
3. **زنجیره ایمپورت اتمی:** دانلود در `CONFIGS.staging` → swap اتمی → پاک‌سازی `.old`؛ شکست دانلود هرگز کانفیگ‌های قبلی را از بین نمی‌برد.
4. **ماشین حالت Cascade با Enum و توابع خالص** (`CascadePhase`, `cascade.py`) — منطق قابل تست بدون نشست گرافیکی.
5. **باندل GResource واحد** (UI/CSS/آیکون/پرچم) — نصب تمیز، بدون فایل پراکنده.
6. **مستندسازی دوزبانه در داک‌استرینگ‌ها** — بسیار کمیاب و ارزشمند.
7. **کد C با کیفیت بالا:** `g_autoptr`، بررسی `GError`، تایم‌اوت سخت ۱۵ ثانیه‌ای روی همهٔ فراخوانی‌های D-Bus، `.clang-format`.

### ۱.۳ Anti-Pattern ها و تنگناهای معماری ⚠️

| # | Anti-pattern | محل | شدت |
|---|---|---|---|
| 1 | **God Object** — `MainWindow` با ۱٬۷۹۷ خط و **۶۵ متد**؛ هم‌زمان ساخت UI، ماشین حالت آبشار (`_cascade_*`)، مانیتور شبکه، تست سرعت، جستجو/فیلتر و رویدادهای D-Bus. نقض صریح SRP و عامل اصلی پیچیدگی شناختی. | `eovpn/main_window.py` | 🔴 بالا |
| 2 | **Service Locator سراسری** — دیکشنری‌های ماژولی `_builder_record` / `_storage_record` / `_session_secrets` و `retrieve()` با خروجی `Any` و کلیدهای رشته‌ای جادویی (`"CM"`, `"proto_cache"`, …). وضعیت پنهان + شکست چندپنجره‌ای. | `eovpn/eovpn_base.py` | 🔴 بالا |
| 3 | **وراثت چندگانه شکننده** — `class MainWindow(Base, Gtk.Builder)` با فراخوانی دستی `Gtk.Builder.__init__(self)`. Composition (`self.builder = Gtk.Builder()`) پاسخ درست است. | `main_window.py`, `settings_window.py` | 🟠 متوسط |
| 4 | **وابستگی حلقوی شکسته‌شده با ایمپورت تاخیری** — `speed_test.py` داخل تابع `parse_ovpn_endpoints` را ایمپورت می‌کند؛ نشانهٔ نبود ماژول مشترک «پارسر». | `eovpn/speed_test.py:56` | 🟠 متوسط |
| 5 | **پروب بک‌اند سنگین روی نخ UI** — `_build_backend_tab` برای خواندن صرفِ شماره نسخه، `NetworkManager(None)`/`OpenVPN3(None)` می‌سازد که هرکدام تا ۱۵ ثانیه D-Bus سنکرون دارند. | `settings_window.py` | 🟠 متوسط |
| 6 | **State سراسری در C** — `static GDBusProxy *UniqueSession`؛ نه thread-safe و نه چندنشسته. | `subprojects/openvpn3/openvpn3.c:40` | 🟠 متوسط |
| 7 | **`GMainLoop` تودرتو در ۴ عملیات NM** — reentrancy + فریز احتمالی تا ۱۵ ثانیه روی نخ UI (watchdog هست ولی فریز باقی است). راه درست: API آسنکرون libnm. | `eovpn_nm.c` | 🟠 متوسط |
| 8 | **دو داستان ساخت موازی** — `pyproject.toml` با `build-backend = "mesonpy"` ادعای wheel دارد در حالی که `meson.build` یک نصب سیستمی است؛ ریسک تعارض `pip`/سیستم. | `pyproject.toml` + `meson.build` | 🟠 متوسط |
| 9 | **کد مرده در ABC** — `get_name()` هم `@abstractmethod` است و هم بدنه‌ای دارد که `self.__NAME__` (نام‌مخدوش‌شده) را برمی‌گرداند؛ هیچ زیرکلاسی از آن استفاده نمی‌کند. | `connection_manager.py:145` | 🟡 پایین |
| 10 | **`Gio.Settings` تکراری** — در هر نمونه‌سازی `Base` دوباره ساخته می‌شود (MainWindow، SettingsWindow، هر ConnectionManager، …). | `eovpn_base.py` | 🟡 پایین |
| 11 | **دو منبع UI واگرا** — `otp.blp` کامیت شده ولی `blueprint-compiler` در زنجیرهٔ Meson نیست؛ فقط `otp.ui` در gresource است → بلوپرینت مرده/واگرا. | `data/ui/` | 🟡 پایین |
| 12 | **APIهای منسوخ GTK4** — `Gtk.MessageDialog`، `Gtk.FileChooserNative`، `Gtk.AboutDialog`، `widget.hide()/show()`، `Gtk.StyleContext.add_provider_for_display` (در GTK5 حذف می‌شوند). | سراسر UI | 🟠 متوسط |
| 13 | **سنتینل رشته‌ای `"null"`** برای کلیدهای GSettings تنظیم‌نشده + هک حذف `-c/--config` از `sys.argv`. | `gschema.xml`, `eovpn_base.py`, `application.py` | 🟡 پایین |

**حکم بخش ۱:** معماری بالاتر از میانگین پروژه‌های دسکتاپ متن‌باز است؛ اما God Object پنجرهٔ اصلی و Service-Locator سراسری، سقف توسعه‌پذیری را پایین نگه داشته‌اند.

---

## ۲. بررسی کیفیت کد (Code Quality & Maintainability)

### ۲.۱ نقاط قوت ✅

- **تایپ‌هینت مدرن و پیوسته:** `str | None`، `dict[str, float | None]`، `frozenset[str]`، `dataclass`، `from __future__ import annotations`.
- **مدیریت خطای منسجم:** I/O و D-Bus همگی در `try/except` با لاگ سطح‌بندی‌شده — بدون `print` و بدون `pass` خاموش (به‌جز موارد کنترل‌شده با `contextlib.suppress`).
- **DRY بهبودیافته نسبت به ادوار قبلی:** `CFFIStringMixin`، پارسر مشترک endpoint، توابع فرمت مشترک (`format_throughput`)، بیلدرهای `_build_*`.
- **۵۶ تست واحد معنادار:** Zip-Slip، zip-bomb، رد HTTP، پارس پروتکل، تایم‌اوت تطبیقی، صف آبشاری، فیلتر سرور، lookup با mock.
- **ابزار کیفیت پیکربندی‌شده:** ruff (`E,W,F,I,N,UP,SIM`)، mypy (`check_untyped_defs = true`)، `.editorconfig`، `.clang-format`.
- **کد C تمیز:** مالکیت حافظه عمدتاً درست، هدر GPL، بررسی خطا در همه نقاط.
- **نام‌گذاری:** سازگار با PEP8 و GTK idiom؛ داک‌استرینگ‌های دوزبانه الگویی.

### ۲.۲ نقض‌های Clean Code / SOLID / DRY / KISS

- **SRP (نقض شدید):** `MainWindow` حداقل ۵ مسئولیت مجزا دارد → باید به `CascadeController`، `NetworkMonitor`، `SpeedTestController` و `ConnectionEventHandler` تفکیک شود.
- **DRY:**
  1. `Settings.all_settings` کپی دستی کلیدهای اسکیماست؛ فقط با تست نگهداری می‌شود (تست به‌جای طراحی — بهتر: Enum یا استخراج خودکار).
  2. سه متد اعلان (`send_connected/disconnected/error_notification`) نزدیک به یکسان‌اند.
  3. `update_network_speed` در هر ثانیه **دو بار** کل `/proc/net/dev` را می‌خواند (یک‌بار اینترفیس VPN، یک‌بار fallback) — یک عبور کافی است.
  4. رشته جادویی `"null"` در ۴ کلید gschema و منطق پراکندهٔ برخورد با آن.
- **DIP:** UI از طریق `retrieve("CM").get("instance")` به پیاده‌سازی چسبیده، نه به اینترفیس تزریق‌شده.
- **KISS:**
  - `on_connection_event` با `if type(result) is list` شاخه‌بندی نوع‌محور می‌کند (باید `isinstance` و بهتر: نوع رویداد صریح/Enum).
  - دیسپچ امضای ناهمگن callback (bool / list / tuple) بین سه لایه پخش شده و باید یک `ConnectionEvent` تایپ‌شده شود.
  - `ovpn_is_auth_required` کل فایل را برای یک زیررشته می‌خواند.

### ۲.۳ پیچیدگی شناختی (Cognitive Complexity)

| تابع | مشکل |
|---|---|
| `MainWindow.on_connection_event` | ترکیب ۴+ حالت (`_cascade_active`, `was_connected`, `manual_disconnect`, `should_reconnect`) + شاخه‌های تودرتو — بالاترین پیچیدگی پروژه |
| `MainWindow._finish_cascade` / `_advance_cascade` / `_on_cascade_timeout` | ماشین حالت پراکنده در ~۱۵ attribute با ۱۵۴+ ارجاع `_cascade_*` |
| `SettingsSignals.on_reset_btn_clicked` | مسئولیت ترکیبی (ریست تنظیمات + حذف دایرکتوری + ریست UI) |
| `Base.validate_and_load.dispatch/glib_func` | closureهای تودرتو با وضعیت مشترک از دو نخ |

**حکم بخش ۲:** کیفیت خط‌به‌خط بالاست؛ بدهی فنی در «مرز مسئولیت‌ها» و «بازنمایی وضعیت» است، نه در سبک کدنویسی.

---

## ۳. بررسی امنیت و شبکه (Security & Network)

### ۳.۱ نقاط قوت امنیتی ✅

- **مدیریت رازها:** رمز فقط در Secret Service (اسکیمای اختصاصی) یا RAM فرّار؛ هرگز dconf/دیسک. بک‌اند NM رمز را `AGENT_OWNED` می‌کند و در صورت شکست اعمال پرچم، **کل ایمپورت را متوقف** می‌کند (نه fallback به دیسک). پاک‌سازی رمز هنگام بستن پنجره (`set_session_password(None)`).
- **ورودی غیرقابل‌اعتماد:** HTTPS-Only + ریدایرکت‌هندلر ضد downgrade؛ سقف ۶۴MiB دانلود / ۲۵۶MiB استخراج / ۲۰هزار ورودی؛ Zip-Slip با `commonpath`؛ `O_NOFOLLOW` + `0600`؛ رد symlink و basename تکراری؛ ایمپورت پوشه با همان سقف.
- **ممیزی کانفیگ:** هشدار پیش از اتصال برای دایرکتیوهای اجرایی (`up`, `down`, `script-security`, `plugin`, `tls-verify`, …).
- **عدم نشت OTP در لاگ** و نگهداری آن فقط در طول تلاش اتصال.
- **تایم‌اوت سخت ۱۵ ثانیه‌ای** همهٔ فراخوانی‌های D-Bus (مقاوم‌سازی در دسترس‌پذیری).
- **Nخ‌امنی GTK:** همهٔ به‌روزرسانی‌های ویجت از نخ اصلی (`GLib.idle_add`).
- **دامنهٔ عملیات مخرب:** فقط پروفایل‌های `managed-by=eovpn-pro` حذف می‌شوند + دیالوگ تأیید با دکمهٔ پیش‌فرض «انصراف».
- **زنجیرهٔ تأمین در طراحی:** هشدار `pip-audit`/CodeQL در مستندات، SHA256SUMS در README/SECURITY.

### ۳.۲ آسیب‌پذیری‌ها و شکاف‌ها ⚠️

| # | یافته | محل | شدت | نگاشت OWASP |
|---|---|---|---|---|
| 1 | **CI امنیتی وجود ندارد.** `SECURITY.md`، `PACKAGING.md`، `CHANGELOG.md` و README ادعای `ci.yml` (pip-audit + CodeQL) و `release.yml` (SHA256SUMS) دارند؛ اما `.github/workflows/` **وجود ندارد** (تأیید API: 404) و هیچ Release هم منتشر نشده. یعنی پویش CVE و مانیفست checksum در عمل صفر است. | `README.md`, `SECURITY.md`, `CHANGELOG.md`, `PACKAGING.md` | 🔴 بحرانی | A06، A08 |
| 2 | **کفِ نسخهٔ آسیب‌پذیر cffi:** الزام `cffi>=1.15.0` اجازهٔ نصب 1.15.0 را می‌دهد که مشمول **CVE-2023-23931** است (رفع در 1.15.1). کف باید به `>=1.16.0` برسد (یا pin دقیق + hash). | `requirements.txt`, `pyproject.toml` | 🟠 متوسط | A06 |
| 3 | **بدون امضای GPG / attestation برای ریلیز** (خود مستندات هم اذعان دارد)؛ و SHA256SUMS نیز چون release.yml نیست تولید نمی‌شود. | `SECURITY.md` | 🟠 متوسط | A08 |
| 4 | **SSRF سبک (کلاینتی):** میزبان private/loopback برای منبع کانفیگ فقط warning می‌گیرد، block نمی‌شود (مستندشده). قابل قبول ولی با `nftables`-sandbox بهتر است. | `eovpn/utils.py` | 🟡 پایین | A05 |
| 5 | **نبود Kill-Switch / ضد نشت DNS** — در قطع تونل، ترافیک به مسیر پیش‌فرض برمی‌گردد (مستندشده). برای یک کلاینت VPN، این مهم‌ترین شکاف «محصولی» است. | معماری کلی | 🟠 متوسط | A05 |
| 6 | **OpenVPN 3:** کلید خصوصی inline و اعتبارنامه از system D-Bus عبور می‌کند (ذات معماری openvpn3؛ مستندشده؛ یکی از دلایل پیش‌فرض بودن NM). | `connection_manager.py` | 🟡 پایین | A02 |
| 7 | **Flatpak:** `--system-talk-name=org.freedesktop.NetworkManager` دسترسی کامل به NM سیستم می‌دهد + وصلهٔ غیرفعال‌کردن ownership-check پلاگین (حداقلی ولی باید دوره‌ای بازبینی شود). | `dist/flatpak/…yml`, `0001-disable-…patch` | 🟡 پایین | A05 |
| 8 | **UAF نهفته در C:** `eovpn_get_managed_active_connection` اشاره‌گر `NMConnection` متعلق به `NMClient` را **بعد از unref کردن client** برمی‌گرداند. امروز تنها فراخوان فقط از `uuid_out` استفاده می‌کند (strdup قبل از unref → ایمن بالفعل)، اما قرارداد تابع خطرناک است و هر فراخوان آینده = UAF. | `subprojects/networkmanager/eovpn_nm.c:70-95` | 🟠 متوسط | — |
| 9 | **نشت GVariant:** در `_get_all_sessions` مقدار `active_sessions` (از `g_variant_get_child_value`) هرگز unref نمی‌شود؛ این تابع در هر poll وضعیت صدا زده می‌شود → نشت تجمعی. | `subprojects/openvpn3/openvpn3.c:74` | 🟡 پایین | — |
| 10 | رمز در RAM به‌صورت `str` معمولی (غیرقابل zero کردن در CPython) — با `bytes` + پاک‌سازی عمدی بهتر است. | `eovpn_base.py` | 🟡 پایین | A02 |
| 11 | `lookup.py`/`utils.py` رشتهٔ User-Agent نسخه را هاردکد کرده‌اند (`eOVPN-Pro/1.5`) — با bump نسخه همگام نمی‌شود. | `eovpn/ip_lookup/lookup.py:17`, `utils.py` | 🟡 پایین | — |

### ۳.۳ احراز هویت و مجوزها

- **احراز هویت:** username/password در Secret Service با attribute `username`؛ OTP/2FA با دیالوگ ۶ رقمی؛ `AUTH_USER` هرگز خالی ارسال نمی‌شود. **خوب.**
- **مجوزها (Authorization):** برنامه در سطح کاربر اجرا می‌شود؛ D-Bus سیستم فقط از طریق سرویس‌های NM/openvpn3؛ حذف پروفایل‌ها به برچسب `managed-by` محدود است. **خوب.**
- **شبکه:** HTTPS اجباری + تایم‌اوت ۱۲s؛ تست سرعت فقط به مقصدهای داخل `.ovpn` (سقف ۱۶ endpoint/کانفیگ و ۱۶ worker). **خوب.**

**حکم بخش ۳:** امنیت لایهٔ برنامه بالاتر از میانگین است؛ شکاف اصلی، «نبود CI/انتشار امنیتی واقعی» و «نبود Kill-Switch» است.

---

## ۴. ارزیابی مستندات (Documentation)

| سند | وضعیت |
|---|---|
| `README.md` | ✅ عالی — دوزبانه، ۷ روش نصب، جدول ورک‌فلو؛ ❌ بج‌های CI/Release به ورک‌فلوهای **ناموجود** لینک می‌دهند |
| `SECURITY.md` | ✅ جامع (گزارش‌دهی، راستی‌آزمایی، محدودیت‌های صادقانه)؛ ❌ بخش Supply-chain ادعای ci.yml/release.yml دارد |
| `PACKAGING.md` | ✅ کامل برای ۵ قالب؛ ❌ بخش ۶ «Automated CI/CD» خیالی است |
| `CHANGELOG.md` | ✅ Keep-a-Changelog؛ ❌ بخش [Unreleased] CI/Release را «افزوده‌شده» توصیف می‌کند |
| `CONTRIBUTING.md`, `docs/ARCHITECTURE.md`, `docs/RELEASE_CHECKLIST.md` | ✅ خوب؛ checklist به CI ناموجود ارجاع می‌دهد |
| `docs/archive/` + README آن | ✅ الگو — عدم‌دقت‌های گزارش‌های تاریخی صادقانه فهرست شده‌اند |
| Docstrings | ✅ دوزبانه و تقریباً کامل در تمام ماژول‌ها |
| راهنمای استقرار | ✅ README + PACKAGING + `eovpn.1` (man) + اسکریپت‌های `scripts/` |
| `tests/README.md`, `po/README.md`, `dist/*/README.md` | ✅ موجود |

**حکم بخش ۴:** از نظر کمیت و کیفیت متن، نمونه‌ای؛ اما **یکپارچگی مستندات با واقعیت مخزن** (ورک‌فلوهای ناموجود) باید فوری اصلاح شود — امروز README به کاربران وعده‌ای می‌دهد که وجود خارجی ندارد.

---

## ۵. ارزیابی انتشار و بسته‌بندی (Packaging Readiness)

| قالب | فایل‌ها | وضعیت | یادداشت |
|---|---|---|---|
| `.deb` | `debian/` (control, rules, postinst/postrm, changelog, copyright, source/format) | ✅ **آماده** | debhelper 13، `hardening=+all`، `dh_auto_test` از `meson test` استفاده می‌کند؛ ❌ `autopkgtest` ندارد |
| `.rpm` | `dist/rpm/eovpn-pro.spec` | ✅ **آماده** | ماکروهای `%meson`، `%check` با desktop-file/appstream، `%find_lang`، filetriggers |
| `.pkg.tar.zst` | `dist/arch/PKGBUILD` + `.SRCINFO` | ✅ **آماده** | دو حالته (درون‌مخزنی/AUR)؛ ❌ `sha256sums=('SKIP')` در حالت انتشار — باید pin شود |
| `.AppImage` | `dist/appimage/build-appimage.sh` | 🟠 **نیمه‌کاره** | «experimental»؛ وابسته به linuxdeploy خارجی؛ کامپایل schema می‌کند ولی **AppRun/wrapper ای که `GSETTINGS_SCHEMA_DIR` را صادر کند نمی‌سازد** (ادعای کامنت خلاف کد است) |
| Flatpak | `dist/flatpak/com.github.mahdi-arts.eovpn-pro.yml` + ۲ patch + cffi manifest | ✅ **آماده ولی سنگین** | NM و openvpn3 از سورس با تگ/هش پین‌شده؛ ❌ بدون CI هرگز ساخته نمی‌شود |
| CI/CD | `.github/workflows/` | ❌ **وجود ندارد** | بزرگ‌ترین شکاف: نه CI، نه Release، نه SHA256SUMS، نه CodeQL، نه pip-audit |
| متادیتا | `scripts/check_project_meta.py` | ✅ خوب | ❌ نسخهٔ PKGBUILD / AppImage script / User-Agent / فلت‌پک را چک نمی‌کند |
| pyproject | `pyproject.toml` | 🟠 دوگانه | `mesonpy` wheel در برابر نصب سیستمی `install_subdir` — باید تکلیف روشن شود یا مستند «غیر-PyPI بودن» اضافه شود |

**حکم بخش ۵:** دستورهای بسته‌بندی برای هر ۵ قالب با کیفیت خوب وجود دارد؛ «آمادگی انتشار» بدون CI/CD و بدون حداقل یک Release واقعی، روی کاغذ باقی می‌ماند.

---

## ۶. امتیازدهی کمی (Scoring)

| شاخص | نمره | توجیه |
|---|---|---|
| کیفیت کد و معماری | **6.5/10** | خط‌به‌خط تمیز و تایپ‌شده؛ اما God Object و Service Locator و پیچیدگی شناختی بالا |
| امنیت | **7/10** | سخت‌سازی لایهٔ برنامه نمونه‌ای؛ کسر نمره: CI امنیتی ناموجود، کف نسخهٔ cffi، نبود Kill-Switch و امضا |
| مستندات | **7.5/10** | کمیت/کیفیت عالی و دوزبانه؛ کسر نمره: توصیف ورک‌فلوهای ناموجود و بج‌های 404 |
| قابلیت توسعه (Scalability) | **5.5/10** | انتزاع بک‌اند مقیاس‌پذیر؛ اما UI تک‌پنجره، وضعیت سراسری و God Object سقف را پایین نگه داشته‌اند |
| آمادگی بسته‌بندی (Packaging) | **6/10** | دستورهای هر ۵ قالب موجود؛ AppImage ناقص، SHA256 SKIP، و مهم‌تر از همه **صفر اتوماسیون** |
| **میانگین کل** | **6.5/10** | پروژه‌ای قوی و قابل‌اعتماد در لایهٔ برنامه؛ نقطهٔ ضعف اصلی، لایهٔ CI/CD و انتشار است |

---

## ۷. طرح اجرایی (Action Plan for Prompt 2) — چک‌لیست ماشین‌خوان

> فرمت: `ID | ACTION | PRIORITY | PATH | توضیح یک‌خطی`
> `ACTION ∈ {CREATE, EDIT, DELETE, MOVE}` — `PRIORITY ∈ {P0, P1, P2}`
> P0 = باید فوراً انجام شود · P1 = در همین چرخه · P2 = بهبود تدریجی

### A. CI/CD و دروازه‌های امنیتی (P0)

| ID | ACTION | PRIORITY | PATH | توضیح |
|---|---|---|---|---|
| A1 | CREATE | P0 | `.github/workflows/ci.yml` | CI کامل: ruff check/format + mypy + unittest روی Python 3.10–3.12 + `pip-audit --strict` + CodeQL + ساخت Meson + smoke-build بسته‌های deb/rpm/arch + `scripts/check_project_meta.py` |
| A2 | CREATE | P0 | `.github/workflows/release.yml` | انتشار خودکار روی تگ `v*.*.*`: بررسی parity نسخه، ساخت ۵ قالب، تولید SHA256SUMS، ساخت GitHub Release + provenance |
| A3 | CREATE | P0 | `.github/workflows/codeql.yml` | (یا داخل A1) تحلیل ایستا CodeQL برای Python و C |
| A4 | EDIT | P0 | `.github/dependabot.yml` | افزودن `versioning-strategy` و گروه‌بندی pip؛ فعال‌کردن به‌روزرسانی اکشن‌ها پس از وجود ورک‌فلوها |

### B. اصلاحات امنیتی

| ID | ACTION | PRIORITY | PATH | توضیح |
|---|---|---|---|---|
| B1 | EDIT | P0 | `requirements.txt` | بالا بردن کف cffi به `>=1.16.0` (رفع CVE-2023-23931) و pin دقیق وابستگی‌ها |
| B2 | EDIT | P0 | `pyproject.toml` | همگام‌سازی کف cffi با B1 |
| B3 | EDIT | P1 | `subprojects/networkmanager/eovpn_nm.c` | حذف بازگشت اشاره‌گر client-owned در `eovpn_get_managed_active_connection` (فقط uuid داپلیکیت برگردد) — رفع UAF نهفته |
| B4 | EDIT | P1 | `subprojects/openvpn3/openvpn3.c` | unref کردن `active_sessions` در `_get_all_sessions` — رفع نشت GVariant |
| B5 | EDIT | P1 | `dist/arch/PKGBUILD` | جایگزینی `sha256sums=('SKIP')` با هش واقعی tarball ریلیز |
| B6 | CREATE | P1 | `docs/SECURITY-ROADMAP.md` (یا بخش در `SECURITY.md`) | برنامهٔ Kill-Switch / ضد نشت DNS (فایروال nftables در قطع تونل) |
| B7 | EDIT | P1 | `eovpn/utils.py` | بلاک سخت‌گیرانه‌تر میزبان‌های private/loopback (قابل دور زدن با گزینهٔ صریح کاربر) |
| B8 | EDIT | P2 | `eovpn/eovpn_base.py` | نگهداری رمز به‌صورت `bytes` در RAM با پاک‌سازی عمدی هنگام بستن پنجره |
| B9 | EDIT | P2 | `eovpn/ip_lookup/lookup.py` + `eovpn/utils.py` | جایگزینی User-Agent هاردکد با مقدار تزریق‌شده از `metadata.json` |

### C. بازآرایی معماری (P1)

| ID | ACTION | PRIORITY | PATH | توضیح |
|---|---|---|---|---|
| C1 | CREATE | P1 | `eovpn/cascade_controller.py` | استخراج کامل ماشین حالت آبشار (~۱۵۴ ارجاع `_cascade_*`) از `MainWindow` به کلاس مستقل |
| C2 | CREATE | P1 | `eovpn/network_monitor.py` | استخراج مانیتور `/proc/net/dev` با یک عبور واحد به کلاس مستقل |
| C3 | EDIT | P1 | `eovpn/main_window.py` | حذف کدهای منتقل‌شده در C1/C2؛ تزریق کنترلرها به‌جای نگهداری state؛ تعویض `type(result) is list` با رویداد تایپ‌شده |
| C4 | CREATE | P1 | `eovpn/events.py` | تعریف `ConnectionEvent` (Enum/dataclass) به‌جای امضای ناهمگن `bool/list/tuple` در callbackها |
| C5 | EDIT | P1 | `eovpn/eovpn_base.py` | جایگزینی Service Locator با AppContext تایپ‌شده (DI)؛ Singleton کردن `Gio.Settings`؛ یکسان‌سازی ۳ متد اعلان؛ حذف sentinel `"null"` |
| C6 | EDIT | P1 | `eovpn/settings_window.py` | جایگزینی `Gtk.FileChooserNative`→`Gtk.FileDialog` و `Gtk.MessageDialog`→`Gtk.AlertDialog`؛ حذف نمونه‌سازی بک‌اند برای خواندن نسخه |
| C7 | EDIT | P1 | `eovpn/connection_manager.py` | حذف کد مردهٔ `get_name` در ABC؛ افزودن `probe_versions()` سبک (classmethod) برای تب Backend |
| C8 | EDIT | P1 | `eovpn/application.py` | حذف هک `sys.argv` و ثبت رسمی آپشن‌های GLib؛ جایگزینی APIهای منسوخ GTK |
| C9 | EDIT | P1 | `subprojects/openvpn3/openvpn3.c` | حذف state سراسری `UniqueSession` و ارسال `session_path` به هر تابع (thread-safe + چندنشسته) |
| C10 | EDIT | P2 | `subprojects/networkmanager/eovpn_nm.c` | مهاجرت تدریجی از `GMainLoop` تودرتو به API آسنکرون libnm (رفع فریز ۱۵ ثانیه‌ای UI) |
| C11 | EDIT | P2 | `eovpn/main_window.py` + `eovpn/settings_window.py` | شکستن وراثت چندگانه `(Base, Gtk.Builder)` به Composition (`self.builder`) |

### D. کیفیت کد و تست

| ID | ACTION | PRIORITY | PATH | توضیح |
|---|---|---|---|---|
| D1 | EDIT | P1 | `eovpn/eovpn_base.py` | تولید `Settings.all_settings` از روی Enum/`__dict__` به‌جای لیست دستی (حذف نگهداری دوتایی) |
| D2 | CREATE | P1 | `tests/test_https_download.py` | تست مسیر HTTPS با mock `urlopen`: رد HTTP، رد ریدایرکت به HTTP، سقف حجم |
| D3 | CREATE | P1 | `tests/test_cascade_state.py` | تست انتقال حالت‌های CascadeController پس از C1 (timeout→advance→settle→next) |
| D4 | EDIT | P1 | `tests/` | افزودن coverage (`.coveragerc` + آستانهٔ ۸۰٪ در CI) |
| D5 | EDIT | P2 | `eovpn/main_window.py` | کاهش پیچیدگی شناختی `on_connection_event`/`_finish_cascade` با جدول انتقال حالت صریح |
| D6 | EDIT | P2 | `eovpn/utils.py` | بهینه‌سازی `ovpn_is_auth_required` (توقف در اولین match) |

### E. پکیجینگ و انتشار

| ID | ACTION | PRIORITY | PATH | توضیح |
|---|---|---|---|---|
| E1 | EDIT | P1 | `dist/appimage/build-appimage.sh` | ساخت AppRun/wrapper واقعی که `GSETTINGS_SCHEMA_DIR` و `XDG_DATA_DIRS` را صادر کند + ادغام linuxdeploy دانلودشده |
| E2 | CREATE | P1 | `debian/tests/control` + `debian/tests/smoke` | افزودن autopkgtest (نصب بسته + اجرای باینری `--help`-مانند + تست‌های آفلاین) |
| E3 | EDIT | P1 | `scripts/check_project_meta.py` | گسترش چک نسخه به PKGBUILD، اسکریپت AppImage، فلت‌پک و User-Agentها |
| E4 | EDIT | P1 | `pyproject.toml` | تعیین تکلیف دوگانگی wheel/سیستم: یا پشتیبانی واقعی mesonpy wheel یا حذف `[build-system]` و مستندسازی |
| E5 | CREATE | P1 | `scripts/build-rpm.sh` | اسکریپت کمکی ساخت RPM (هم‌تراز `build-deb.sh`/`build-flatpak.sh`) برای CI |
| E6 | EDIT | P2 | `dist/flatpak/com.github.mahdi-arts.eovpn-pro.yml` | بررسی به‌روزرسانی runtime و پین‌های git پس از اولین ریلیز |

### F. همگام‌سازی مستندات با واقعیت

| ID | ACTION | PRIORITY | PATH | توضیح |
|---|---|---|---|---|
| F1 | EDIT | P0 | `README.md` | پس از A1/A2، بج‌ها و جدول ورک‌فلو واقعی می‌شوند؛ تا آن زمان بج‌ها حذف/غیرفعال یا به «نداریم» اصلاح شوند |
| F2 | EDIT | P0 | `CHANGELOG.md` | انتقال اقلام CI/Release از [Unreleased] به نسخهٔ واقعی پس از merge |
| F3 | EDIT | P0 | `PACKAGING.md` (بخش ۶) و `SECURITY.md` (Supply chain) | بازنویسی بر اساس رفتار واقعی ورک‌فلوهای ساخته‌شده |
| F4 | EDIT | P1 | `docs/RELEASE_CHECKLIST.md` | افزودن گام‌های CI/Release جدید (تگ، SHA256SUMS، provenance) |
| F5 | EDIT | P2 | `CONTRIBUTING.md` | افزودن راهنمای اجرای `run_program_debug.py` و ساخت از سورس برای توسعه‌دهندگان |

### G. یکپارچه‌سازی UI/داده

| ID | ACTION | PRIORITY | PATH | توضیح |
|---|---|---|---|---|
| G1 | EDIT | P1 | `data/ui/` + `meson.build` | افزودن `blueprint-compiler` به زنجیرهٔ ساخت یا حذف `otp.blp` (رفع دوگانگی منبع) |
| G2 | EDIT | P2 | `data/com.github.mahdi-arts.eovpn-pro.desktop` | افزودن `Keywords` و `X-GNOME-UsesNotifications=true` |
| G3 | EDIT | P2 | `eovpn/dialogs/otp.py` | پشتیبانی paste کد ۶ رقمی در یک فیلد |

---

## 📋 بلوک ورودیِ پرامپت بعدی (Input Command)

```
EXECUTE PLAN=R2-2026-08 SCOPE=eOVPN-Pro@f2c2df9
P0: A1 A2 A3 A4 B1 B2 F1 F2 F3
P1: B3 B4 B5 B6 B7 C1 C2 C3 C4 C5 C6 C7 C8 C9 D1 D2 D3 D4 E1 E2 E3 E4 E5 F4 G1
P2: B8 B9 C10 C11 D5 D6 E6 F5 G2 G3
RULE: هر آیتم = یک کامیت مستقل با پیام `fix|feat|refactor|ci|docs(<scope>): <ID> <توضیح>` ·
پس از هر آیتم: اجرای `python3 -m unittest discover -s tests` + `python3 scripts/check_project_meta.py` ·
خروجی نهایی: PR از `arena/01a0290e-eovpn-pro` به `master`
```

---

*یا علی مدد 💚*
