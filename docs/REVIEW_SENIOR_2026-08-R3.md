# 🔍 بازبینی فنی سطح Senior (دور سوم — R3) — مخزن eOVPN-Pro

**تاریخ بازبینی:** 2026-08-22 · **شاخه:** `arena/01a02949-eovpn-pro` (کامیت پایه `9a6b220` از `master` = ادغام PR#11)
**نسخه:** 1.5.0 · **مجوز:** GPL-3.0-or-later · **App ID:** `com.github.mahdi-arts.eovpn-pro`
**نقش بازبین:** مهندس Full-Stack ارشد + مدیر سیستم لینوکس ارشد + متخصص امنیت سایبری + معمار نرم‌افزار
**روش:** خواندن کامل کدبیس (Python + C + Meson + پکیجینگ)، **اجرای واقعی** تست‌ها/lint/تایپ‌چک، راستی‌آزمایی وضعیت با `git ls-files` و فایل‌سیستم

> این گزارش، بازبینی **مستقل** سوم است. گزارش‌های R1 و R2 در `docs/REVIEW_SENIOR_2026-08.md` و
> `docs/REVIEW_SENIOR_2026-08-R2.md` موجود‌اند. وضعیت هر موردِ R2 مجدداً راستی‌آزمایی شده و
> نتیجه در جدول پایین آمده است. **اصل راهنما:** چیزی که از قبل درست است را تغییر نمی‌دهیم؛ صرفاً مشکلات واقعی را گزارش می‌کنیم.

---

## 🧪 راستی‌آزمایی‌های اجراشده (Evidences)

| بررسی | نتیجه |
|---|---|
| `python3 -m unittest discover -s tests` | ✅ **81/81 OK** (0.028s) — *(نه ۵۶؛ شمارش قدیمی در مستندات باقی مانده)* |
| `python3 -m ruff check .` | ✅ **All checks passed!** |
| `python3 -m ruff format --check .` | ✅ **64 files already formatted** |
| `python3 -m mypy --ignore-missing-imports eovpn` | ✅ **Success: no issues found in 26 source files** |
| `python3 scripts/check_project_meta.py` | ✅ `All metadata checks passed (version 1.5.0)` |
| `python3 -m compileall eovpn tests` | ✅ بدون خطا |
| `git ls-files \| grep -i workflow` | ❌ **خروجی خالی — هیچ فایل ورک‌فلو tracked نیست** |
| `ls .github/workflows/` | ❌ **پوشه وجود ندارد** |
| `gh api repos/Mahdi-Arts/eOVPN-Pro/releases` | ❌ **هیچ Release منتشرشده‌ای وجود ندارد** |
| `test_` functions واقعی | **۸۱ تابع** (افزایش از ۵۶) |

### ↻ راستی‌آزمایی کامل موارد R2 (همگی بررسی شدند)

| گروه R2 | وضعیت فعلی |
|---|---|
| **A1–A3** (ورک‌فلوهای `ci.yml` / `codeql.yml` / `release.yml`) | ❌ **هنوز ساخته نشده‌اند** — یافتهٔ اصلی این گزارش |
| **A4** (Dependabot گروهی + `versioning-strategy`) | ✅ انجام شد |
| **B1/B2** (کف cffi → `>=1.16.0`) | ✅ در `requirements.txt` و `pyproject.toml` |
| **B3** (UAF در `eovpn_nm.c`) | ✅ حل شد — `eovpn_get_managed_active_uuid` فقط UUID کپی‌شده برمی‌گرداند، نه شیء connection |
| **B4** (نشت GVariant در `_get_all_sessions`) | ✅ حل شد — `g_autoptr` + `g_variant_iter_new` ارجاع خودش را می‌گیرد |
| **B5** (PKGBUILD `sha256sums=SKIP`) | 🟡 حالت دوگانه؛ `SKIP` فقط در حالت AUR/release (با کامنت صادقانه) — CI در حالت درون‌مخزنی免疫 |
| **B6** (سند نقشه راه امنیتی) | ✅ `docs/SECURITY-ROADMAP.md` موجود (Kill-Switch/DNS-leak برای 1.6.0) |
| **B7** (SSRF سخت) | ✅ `is_hard_blocked_source_host` اضافه شد |
| **B8** (رمز به‌صورت `bytes` پاک‌شو) | ✅ `bytearray` + `_wipe_session_password` |
| **B9** (User-Agent از متادیتا) | ✅ `app_version()` تزریق‌شده |
| **C1/C2/C3/C4** (استخراج cascade/monitor/events) | ✅ همگی ایجاد و به `main_window` متصل شدند (۱۷۹۷→۱۳۳۱ خط) |
| **C5** (Singleton `Gio.Settings`) | ✅ `_get_gs_settings()` پروسه‌ای |
| **C6** (APIهای منسوخ GTK) | ✅ لایهٔ `ui_compat.py` (FileDialog/AlertDialog با fallback) — طراحی درست، **نیازی به تغییر ندارد** |
| **C7** (`probe_version` / حذف کد مرده) | ✅ classmethod سبک اضافه شد؛ `get_name` در ABC اکنون بدون بدنه |
| **C8** (هک `sys.argv`) | ✅ `--config` به‌عنوان `add_main_option` رسمی ثبت شد |
| **C9** (state سراسری `UniqueSession` در C) | ✅ حذف شد؛ همهٔ عملیات‌ها `session_object` صریح می‌گیرند (thread-safe) |
| **C10** (GMainLoop روی نخ UI) | ✅ `_dispatch_off_ui_thread` عملیات مسدود را به نخ کارگر می‌برد |
| **D1/D2/D3/D4** (تست‌ها/coverage) | ✅ ۵۶→۸۱ تست؛ `app_version`، HTTPS، cascade-state، network-monitor اضافه شدند |
| **D6** (`ovpn_is_auth_required` توقف زودهنگام) | ✅ |
| **E1** (AppRun واقعی) | ✅ اسکریپت `GSETTINGS_SCHEMA_DIR`/`XDG_DATA_DIRS`/`PYTHONPATH` را صادر می‌کند |
| **E2** (autopkgtest) | ✅ `debian/tests/{control,smoke}` موجود |
| **E3** (check_project_meta گسترش‌یافته) | ✅ PKGBUILD/AppImage/.SRCINFO/metainfo/README را چک می‌کند |
| **E5** (`build-rpm.sh`) | ✅ موجود |
| **G1** (blueprint واگرا) | ✅ حل شد — `otp.blp` حذف شد، فقط `.ui` در gresource |
| **G2** (Keywords + notifications در desktop) | ✅ |

> **نتیجه:** تقریباً همهٔ موارد R2 اجرا شده‌اند. تنها شکافِ واقعی و بحرانی، **نبود CI/CD** و پیامد مستنداتی آن است.

---

## ۱. تحلیل معماری و ساختار (Architecture & Structure)

### ۱.۱ نقاط قوت ✅ (بدون نیاز به تغییر)

1. **لایه‌بندی تمیز UI / Domain / Native** و جداسازی منطق خالص از GTK — این طراحی، دلیل اصلی سبز بودن **۸۱ تست آفلاین** بدون نشست گرافیکی است؛ بهترین تصمیم معماری پروژه.
2. **انتزاع بک‌اند درست:** `ConnectionManager(ABC)` + `NetworkManager`/`OpenVPN3` + fallback امن در `create_connection_manager()`. افزودن بک‌اند سوم کم‌هزینه است.
3. **استخراج ماشین‌های حالت:** `cascade_controller.py` (۵۸۸ خط) و `network_monitor.py` (۱۵۴ خط) منطق بلندمدت را با وابستگی‌های تزریق‌شده نگه می‌دارند؛ `main_window.py` از ۱۷۹۷ به ۱۳۳۱ خط تقلیل یافت و اکنون کنترلرها را هماهنگ می‌کند نه خودش اجرا می‌کند.
4. **زنجیرهٔ ایمپورت اتمی** (staging → swap → پاک‌سازی `.old`) — شکست دانلود هرگز کانفیگ‌های قبلی را از بین نمی‌برد.
5. **ماشین حالت Cascade با Enum و توابع خالص** (`cascade.py`) — قابل تست.
6. **باندل GResource واحد** (UI/CSS/آیکون/۲۵۶ پرچم) — نصب تمیز.
7. **کد C با کیفیت بالا:** `g_autoptr`، بررسی `GError`، تایم‌اوت سخت ۱۵s، عدم state سراسری (thread-safe + چندنشسته)، `.clang-format`.

### ۱.۲ Anti-Patternهای باقی‌مانده ⚠️

| # | یافته | محل | شدت | توضیح |
|---|---|---|---|---|
| 1 | **`MainWindow` همچنان بزرگ (۱۳۳۱ خط / ~۶۵ متد)** | `eovpn/main_window.py` | 🟡 متوسط | تقلیل چشمگیری نسبت به ۱۷۹۷ خط داشته، ولی هنوز هم‌زمان هماهنگ‌کنندهٔ UI + wiring آبشار + رویداد D-Bus است. این یک **بهبود تدریجی** است، نه اشکال بحرانی؛ به `on_connection_event` با جدول انتقال حالت صریح می‌توان کم‌رنگ‌ترش کرد. |
| 2 | **Service-Locator پویا (`retrieve()` با خروجی `Any`)** | `eovpn/eovpn_base.py` | 🟡 پایین | برای یک برنامهٔ تک‌نشستهٔ دسکتاپ قابل قبول است و در `ARCHITECTURE.md` صادقانه مستند شده. فقط در صورت چندنشسته‌شدن باید به DI تایپ‌شده ارتقا یابد. **امروز نیازی به تغییر ندارد.** |

**حکم بخش ۱:** معماری بالاتر از میانگین پروژه‌های دسکتاپ متن‌باز است و بازآرایی‌های R2 اثربخش بوده‌اند. هیچ بازنویسی معماری ضروری وجود ندارد.

---

## ۲. بررسی کیفیت کد (Code Quality & Maintainability)

### ۲.۱ نقاط قوت ✅

- **دروازه‌های کیفیت همگی سبز:** `ruff check` ✓، `ruff format --check` ✓ (۶۴ فایل)، `mypy` ✓ (۲۶ فایل، بدون ایراد)، ۸۱ تست ✓، `check_project_meta` ✓.
- **تایپ‌هینت مدرن و پیوسته:** `str | None`، `frozenset[str]`، `dataclass`، `from __future__ import annotations`.
- **مدیریت خطای منسجم:** I/O و D-Bus همگی در `try/except` با لاگ سطح‌بندی‌شده؛ بدون `print` و بدون `pass` خاموش.
- **DRY:** `Settings.all_settings` از روی کلاس تولید می‌شود (منبع واحد حقیقت)، سه متد اعلان به `_send_notification` یکسان شدند، `network_monitor` فقط **یک عبور** از `/proc/net/dev` دارد.
- **داک‌استرینگ‌های دوزبانه** در سراسر ماژول‌ها — الگویی و ارزشمند.
- **نام‌گذاری** سازگار با PEP8 و idiom GTK.

### ۲.۲ نقض‌های جزئی 🟡

- `self.__NAME__` در `ConnectionManager.__init__` ست می‌شود اما زیرکلاس‌ها `get_name()` را hardcode برمی‌گردانند (کد مردهٔ بی‌اثر). **نکتهٔ پیش‌پاافتاده — ارزش دست‌زدن ندارد.**
- `on_connection_event` همچنان پیچیدگی شناختی بالایی دارد (شاخه‌های تودرتو). کاهش آن به جدول انتقال حالت یک **بهبود تدریجی P2** است، نه اشکال.

**حکم بخش ۲:** کیفیت کد در سطح بالا و آمادهٔ تولید است. بدهی فنی باقی‌مانده از نوع «نظم بیشتر» است نه «اشکال». **تغییر کد ضروری وجود ندارد.**

---

## ۳. بررسی امنیت و شبکه (Security & Network)

### ۳.۱ نقاط قوت ✅ (لایهٔ برنامه نمونه‌ای است)

- **رازها:** Secret Service (اسکیمای اختصاصی) + RAM فرّار به‌صورت `bytearray` با پاک‌سازی فعالانه؛ هرگز dconf/دیسک. بک‌اند NM رمز را `AGENT_OWNED` می‌کند و در صورت شکست اعمال پرچم، **کل ایمپورت را متوقف** می‌کند.
- **ورودی غیرقابل‌اعتماد:** HTTPS-Only + ریدایرکت‌هندلر ضد downgrade؛ سقف ۶۴/۲۵۶ MiB؛ Zip-Slip با `commonpath`؛ `O_NOFOLLOW` + `0600`؛ رد symlink و basename تکراری؛ SSRF با `is_hard_blocked_source_host` (block سخت، نه فقط warning).
- **ممیزی کانفیگ:** هشدار برای دایرکتیوهای اجرایی (`up`/`down`/`script-security`/`plugin`/…).
- **مقاوم‌سازی در دسترس‌پذیری:** تایم‌اوت سخت ۱۵s روی همهٔ فراخوانی‌های D-Bus.
- **نخ‌امنی GTK:** همهٔ به‌روزرسانی‌های ویجت از `GLib.idle_add`.
- **بومی C:** UAF و نشت GVariant هر دو حل شدند؛ state سراسری حذف شد (thread-safe).
- **زنجیرهٔ تأمین در طراحی:** SHA256SUMS برنامه‌ریزی‌شده، Dependabot گروهی فعال.

### ۳.۲ شکاف‌ها و مسیر راه ⚠️

| # | یافته | محل | شدت | توضیح |
|---|---|---|---|---|
| 1 | **هیچ CI امنیتی اجرا نمی‌شود.** | `.github/workflows/` (ناموجود) | 🔴 بحرانی | وعدهٔ `pip-audit` و CodeQL در `SECURITY.md` داده شده ولی در عمل صفر است. یعنی کشف CVE و تحلیل ایستا امروز رخ نمی‌دهد. **همان شکاف CI/CD است.** |
| 2 | **نبود SHA256SUMS/امضای ریلیز** | `release.yml` (ناموجود) | 🟠 متوسط | دستور `sha256sum -c SHA256SUMS` در README برای کاربران غیرقابل اجراست چون هیچ ریلیزی منتشر نمی‌شود. |
| 3 | **نبود Kill-Switch / ضد نشت DNS** | معماری | 🟠 متوسط (مسیر راه) | در `SECURITY-ROADMAP.md` برای نسخهٔ ۱.۶.۰ برنامه‌ریزی شده است. یک مورد محصولی واقعی است ولی **به‌عنوان مسیر راه ردیابی می‌شود، نه اشکال فعلی.** |
| 4 | **مجوز گستردهٔ Flatpak (`--system-talk-name=org.freedesktop.NetworkManager`)** | `dist/flatpak/*.yml` | 🟡 پایین (مسیر راه) | در `SECURITY-ROADMAP.md` برای تنگ‌تر شدن با `xdg-dbus-proxy` ثبت شده. |
| 5 | رمز به‌صورت `bytearray` (بهتر از str ولی CPython همچنان کپی می‌تواند بسازد) | `eovpn_base.py` | 🟡 بسیار پایین | بهبود ساده‌لوحانه؛ ارزش دست‌زدن ندارد. |

### ۳.۳ احراز هویت و مجوزها ✅

- احراز هویت: username/password در Secret Service؛ OTP/2FA با دیالوگ؛ `AUTH_USER` هرگز خالی ارسال نمی‌شود. **خوب.**
- مجوزها: اجرای سطح کاربر؛ حذف پروفایل فقط با برچسب `managed-by=eovpn-pro` + دیالوگ تأیید با پیش‌فرض «انصراف». **خوب.**
- شبکه: HTTPS اجباری + تایم‌اوت ۱۲s؛ تست سرعت فقط به مقصدهای داخل `.ovpn` (سقف ۱۶). **خوب.**

**حکم بخش ۳:** لایهٔ امنیت برنامه نمونه‌ای است. شکاف واقعی، «خاموش بودن اتوماسیون امنیتی (CI/CodeQL/pip-audit/ریلیز)» است — نه کد.

---

## ۴. ارزیابی مستندات (Documentation)

| سند | وضعیت |
|---|---|
| `README.md` | ✅ عالی و دوزبانه؛ ❌ **بج‌های CI/Release به ورک‌فلوهای ناموجود لینک می‌دهند (۴۰۴)** و شمارش تست «۵۶» به‌جای ۸۱ است. |
| `docs/ARCHITECTURE.md` | ✅ نمونه — لایه‌ها، تصمیمات، نقشهٔ ماژول. |
| `SECURITY.md` | ✅ جامع؛ ❌ بخش Supply-chain ادعای اجرای `ci.yml`/`codeql.yml` دارد (ناموجود). |
| `PACKAGING.md` | ✅ کامل برای ۵ قالب؛ ❌ بخش ۶ «سه ورک‌فلو» خیالی است + شمارش ۵۶ تست. |
| `CHANGELOG.md` | ✅ Keep-a-Changelog؛ ❌ بخش `[Unreleased]`، CI/CodeQL/release.yml را «افزوده‌شده» توصیف می‌کند (هنوز ناموجود) + شمارش ۵۶. *نکتهٔ صادقانه در خط ۱۵۷ به تعویق اشاره دارد.* |
| `docs/RELEASE_CHECKLIST.md` | ✅ **تنها سند صادقانه** — چک‌باکس باز «`.github/workflows/` present». |
| `docs/SECURITY-ROADMAP.md` | ✅ عالی — مسیر راه صریح برای ۱.۶.۰. |
| `CONTRIBUTING.md`, `eovpn.1`, `po/`, `tests/`, `dist/*/README.md` | ✅ موجود و خوب. |
| Docstrings | ✅ دوزبانه و تقریباً کامل. |

**حکم بخش ۴:** از نظر کمیت/کیفیت متن، نمونه‌ای است. تنها مشکل **«پیشگوییِ اتوماسیونی که وجود خارجی ندارد»** + **drift شمارش تست (۵۶→۸۱)** است. هر دو با ساخته‌شدن ورک‌فلوها و یک ویرایش کوچک حل می‌شوند.

---

## ۵. ارزیابی انتشار و بسته‌بندی (Packaging Readiness)

| قالب | فایل‌ها | وضعیت | یادداشت |
|---|---|---|---|
| `.deb` | `debian/` | ✅ **آماده** | debhelper 13، `hardening=+all`، `dh_python3`، `autopkgtest` (smoke) |
| `.rpm` | `dist/rpm/eovpn-pro.spec` | ✅ **آماده** | ماکروهای `%meson`، `%check`، `%find_lang`، filetriggers |
| `.pkg.tar.zst` | `dist/arch/PKGBUILD` + `.SRCINFO` | ✅ **آماده** | دوحالته؛ `SKIP` فقط در حالت AUR (زمان انتشار پر می‌شود) |
| `.AppImage` | `dist/appimage/build-appimage.sh` | ✅ **آماده** (R1/R2 ناقص بود) | AppRun واقعی، صادر کردن schema/data/python paths |
| Flatpak | `dist/flatpak/*.yml` + پچ‌ها + cffi manifest | ✅ **آماده** | NM/openvpn3 از سورس با تگ/هش پین‌شده |
| **CI/CD** | `.github/workflows/` | ❌ **وجود ندارد** | **بزرگ‌ترین و تنها شکاف جدی** |
| متادیتا | `scripts/check_project_meta.py` | ✅ خوب | نسخه‌ها/اسکیما/gresource همگانی |
| AppStream/desktop | metainfo.xml, .desktop | ✅ خوب | `content_rating`، `releases`، `Keywords`، `X-GNOME-UsesNotifications` |

**حکم بخش ۵:** دستورهای بسته‌بندی برای هر ۵ قالب با کیفیت خوب موجود و پس از R1/R2 کامل شده‌اند. آمادگی انتشار منحصراً گروگانِ نبود CI/CD و حداقل یک ریلیز واقعی است.

---

## ۶. امتیازدهی کمی (Scoring)

| شاخص | نمره | توجیه |
|---|---|---|
| کیفیت کد و معماری | **8/10** | دروازه‌های کیفیت همگی سبز؛ ruff/mypy/۸۱ تست؛ God Object تقلیل یافته. (نسبت به R2: ۶.۵→۸) |
| امنیت | **7.5/10** | لایهٔ برنامه نمونه‌ای؛ UAF/نشت حل شد. کسر نمره: CI امنیتی خاموش، نبود Kill-Switch و امضای ریلیز. (۷→۷.۵) |
| مستندات | **7.5/10** | کمیت/کیفیت عالی و دوزبانه؛ کسر: وعدهٔ اتوماسیون ناموجود + drift تست. |
| قابلیت توسعه (Scalability) | **6.5/10** | انتزاع بک‌اند و استخراج کنترلرها خوب؛ Service-Locator پویا سقف را پایین نگه داشته. (۵.۵→۶.۵) |
| آمادگی بسته‌بندی (Packaging) | **6.5/10** | هر ۵ قالب آماده و کامل؛ کسر: **صفر اتوماسیون CI/Release** + `SKIP` در AUR. (۶→۶.۵) |
| **میانگین کل** | **7.2/10** | کدبیس در سطح آمادهٔ تولید؛ نقطهٔ ضعف متمرکز و تنها، لایهٔ CI/CD است. (R2: ۶.۵→۷.۲) |

> ارتقای نمره نسبت به R2 واقعی است و ناشی از اجرای موفق برنامهٔ R2 است — به‌جز ورک‌فلوها.

---

## ۷. طرح اجرایی (Action Plan for Prompt 2) — چک‌لیست ماشین‌خوان

> **اصل کلیدی این گزارش:** کدبیس **نیازی به تغییر ندارد**. تقریباً همهٔ موارد R2 اجرا شده‌اند.
> طرح زیر، تنها کارِ واقعاً ضروری (CI/CD + همگام‌سازی مستندات) را پوشش می‌دهد. اندازهٔ کوچک لیست، نشانهٔ سلامت پروژه است — نه غفلت.
>
> فرمت: `ID | ACTION | PRIORITY | PATH | توضیح یک‌خطی`
> `ACTION ∈ {CREATE, EDIT}` — `PRIORITY ∈ {P0, P1}`
> P0 = باید فوراً (اتوماسیون/امنیت) · P1 = همگام‌سازی مستندات پس از P0

### A. CI/CD و دروازه‌های امنیتی (P0 — تنها کار بحرانی)

| ID | ACTION | PRIORITY | PATH | توضیح یک‌خطی |
|---|---|---|---|---|
| A1 | CREATE | P0 | `.github/workflows/ci.yml` | ورک‌فلوی CI: ماتریس Python 3.10/3.11/3.12 → `ruff check` + `ruff format --check` + `mypy` + `unittest discover` + coverage؛ سپس `pip-audit --strict`؛ سپس `scripts/check_project_meta.py`؛ سپس `meson setup/compile/install` با `desktop-file-validate` و `appstreamcli validate`؛ و در انتها smoke-build بسته‌های deb/rpm/arch (در کانتینر بومی). همهٔ جزئیات دقیقاً در README/PACKAGING/CHANGELOG توصیف شده‌اند. |
| A2 | CREATE | P0 | `.github/workflows/codeql.yml` | تحلیل ایستای CodeQL (security-extended) روی زبان‌های `python` و `c-cpp`؛トリگر push/PR + `schedule: weekly`. |
| A3 | CREATE | P0 | `.github/workflows/release.yml` | تریگر تگ `v*.*.*`: اجرای `check_project_meta.py` برای parity نسخه → ساخت deb/rpm/pkg.tar.zst/AppImage/Flatpak → تولید `SHA256SUMS` → `actions/attest-build-provenance` → انتشار GitHub Release با یادداشت خودکار. |

### B. همگام‌سازی مستندات با واقعیت (P1 — پس از A1–A3 تقریباً خود‌به‌خود)

| ID | ACTION | PRIORITY | PATH | توضیح یک‌خطی |
|---|---|---|---|---|
| B1 | EDIT | P1 | `README.md` | اصلاح شمارش تست «۵۶»→«۸۱» (سه‌جا: خطوط ۱۶۸، ۱۷۲، ۲۰۱). *بج‌های CI/Release پس از A1/A3 خود‌به‌خود واقعی می‌شوند.* |
| B2 | EDIT | P1 | `CHANGELOG.md` | اصلاح «۵۶ تست»→«۸۱ تست» (خط ۱۶)؛ هنگام merge، انتقال مواردهای CI/Release از `[Unreleased]` به نسخهٔ واقعی. |
| B3 | EDIT | P1 | `PACKAGING.md` | اصلاح «۵۶ تست»→«۸۱ تست» (خط ۱۵۲). *بخش ۶ پس از A1/A3 خود‌به‌خود واقعی می‌شود.* |

### مواری که **عمداً در لیست نیست** (تایید عدم‌نیاز به تغییر)

- **کد Python/C** — هیچ فایلی نیاز به ویرایش ندارد (mypy/ruff/۸۱ تست سبز؛ UAF/نشت/state سراسری حل شده‌اند).
- **`ui_compat.py`** — لایهٔ compat برای FileDialog/AlertDialog با fallback، طراحی درست است؛ تغییر نمی‌خواهد.
- **`eovpn_base.py` Service-Locator** — برای دسکتاپ تک‌نشسته قابل قبول و مستند است.
- **Kill-Switch / DNS-leak / Flatpak tightening** — در `SECURITY-ROADMAP.md` برای ۱.۶.۰ ردیابی می‌شوند؛ مسیر راه، نه اشکال فعلی.
- **PKGBUILD `sha256sums=SKIP`** — حالت AUR/release؛ با اولین تگ واقعی پر می‌شود. حالت درون‌مخزنیِ CI ایمن است. **اقدامِ زمان انتشار، نه کد.**

---

## 📋 بلوک ورودیِ پرامپت بعدی (Input Command)

```
EXECUTE PLAN=R3-2026-08 SCOPE=eOVPN-Pro@9a6b220 BRANCH=arena/01a02949-eovpn-pro
PRINCIPLE: کدبیس آمادهٔ تولید است؛ فقط CI/CD بساز و مستندات را همگام کن. کد را تغییر نده.

P0 (critical — اتوماسیون/امنیت):
  A1 CREATE .github/workflows/ci.yml     # CI کامل مطابق توصیف README/PACKAGING
  A2 CREATE .github/workflows/codeql.yml # CodeQL security-extended (python + c-cpp)
  A3 CREATE .github/workflows/release.yml# ساخت ۵ قالب + SHA256SUMS + provenance روی تگ v*.*.*

P1 (doc sync — پس از P0):
  B1 EDIT   README.md        # 56→81 تست (خط ۱۶۸/۱۷۲/۲۰۱)؛ بج‌ها با A1/A3 واقعی می‌شوند
  B2 EDIT   CHANGELOG.md     # 56→81 (خط ۱۶)؛ انتقال [Unreleased] به نسخه هنگام merge
  B3 EDIT   PACKAGING.md     # 56→81 (خط ۱۵۲)

VERIFY (پس از هر آیتم):
  - python3 -m ruff check . && python3 -m ruff format --check .
  - python3 -m mypy --ignore-missing-imports eovpn
  - python3 -m unittest discover -s tests   # انتظار: 81 OK
  - python3 scripts/check_project_meta.py
  - بعد از A1-A3: اجرای واقعی ورک‌فلوها روی PR برای تأیید سبز شدن بج‌ها

COMMIT-MSG: ci(<scope>): <ID> <توضیح> | docs(<scope>): <ID> <توضیح>
PR-TARGET: master از arena/01a02949-eovpn-pro
```

---

*یا علی مدد 💚*
