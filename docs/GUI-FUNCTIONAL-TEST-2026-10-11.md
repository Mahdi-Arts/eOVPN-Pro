# گزارش تست اجرایی و GUI — eOVPN-Pro

## دامنه

تست‌ها روی working tree ریشه انجام شدند. اتصال واقعی VPN، تغییر NetworkManager/D-Bus و import عملیاتی کانفیگ عمداً اجرا نشدند.

## نتایج

| سناریو | نتیجه | توضیح |
|---|---|---|
| import ماژول‌های اصلی | PASS | application، domain، backend facade و lookup import شدند |
| `--help`/entry-point | COMPLETED | launcher پیکربندی‌شده با `PYTHONPATH` ریشه، exit code صفر و نمایش گزینه‌ها اجرا شد؛ اجرای مستقیم build بدون نصب به‌علت نبود package در prefix موقت، معیار محصول نصب‌شده محسوب نمی‌شود |
| GSettings schema | PASS | schema با `glib-compile-schemas --strict` معتبر است؛ کلید `language` با schema محلی خوانده شد |
| GResource bundle | PASS | resource bundle با `glib-compile-resources` تولید شد |
| تست‌های unit/offline | PASS | ۱۰۳ تست موفق؛ شامل گزارش capabilityهای backend، DCO و probeهای fail-safe |
| archive/path/security utilities | PASS | ZIP Slip، حجم archive/folder، HTTPS و directive checks پوشش داده شدند |
| backend optional detection | PARTIAL / BLOCKED | CFFI جدید با نماد `get_last_error` ساخته و artifactهای ریشه به‌صورت کنترل‌شده با آن هم‌تراز شدند؛ اتصال واقعی همچنان به سرویس و پیکربندی سیستم وابسته است |
| Reset/Restore مسیر منطقی | PASS آفلاین / GUI BLOCKED | snapshot محلی با مجوز محدود و Restore آخرین snapshot پیاده‌سازی شد؛ Secret Service عمداً backup نمی‌شود و اجرای تعاملی نیازمند desktop واقعی است |
| OpenVPN3 backend | UNKNOWN/BLOCKED | Python binding و dependency در محیط موجود نیست |
| startup ایزولهٔ GTK/X11 | COMPLETED | اجرای ۱۰ثانیه‌ای با `GDK_BACKEND=x11`، `GSETTINGS_BACKEND=memory` و XDG مسیرهای موقت به UI رسید و بدون GTK/ListBox/Adwaita critical یا traceback پایان یافت؛ timeout طبیعی بود |
| visual polish ایزوله | COMPLETED | screenshot پنجرهٔ واقعی پس از اصلاح CSS/GTK در `/tmp/eovpn-design-after.png` ثبت شد؛ toolbar، empty state، panel separation، traffic card و Connect action خوانا و هم‌تراز هستند |
| Backend Settings capability panel | COMPLETED | تشخیص read-only از کلید واقعی DCO جدا شده؛ DCO فقط با OpenVPN 3 قابل‌استفاده فعال می‌شود و unavailable بودن همراه علت نمایش داده می‌شود |
| keyboard focus و menu trigger | COMPLETED | focus با Tab روی کنترل‌ها و hamburger قابل مشاهده شد و menu action با Enter فعال شد؛ تست انتخاب همهٔ آیتم‌های منو و بازشدن Settings هنوز کامل نیست |
| GUI visual acceptance | BLOCKED / OWNER-VERIFIED pending | startup ایزوله اثبات شد؛ اجرای native در نشست فعلی به پنجرهٔ قابل screenshot/automation نرسید، بنابراین بررسی تعاملی کامل منوها، Settings، About، زبان فارسی، speed test و auto-connect و تأیید مالک هنوز انجام نشده است |
| VPN connect/disconnect | OWNER-VERIFIED pending | عمداً انجام نشده است |

## سناریوهای آمادهٔ اجرای گرافیکی پس از فراهم‌شدن desktop

۱. startup در English و فارسی، تغییر زبان و restart ایمن؛ ۲. Settings در سه تب و Reset؛ ۳. About شامل release/legal/privacy/support؛ ۴. import و نمایش ردیف‌ها؛ ۵. speed test و مشاهدهٔ هم‌زمان مقادیر؛ ۶. فیلتر TCP/UDP/Favorites/Online/Offline و اطمینان از باقی‌ماندن latency؛ ۷. sort و انتخاب سریع‌ترین؛ ۸. auto-connect با زمان‌سنج حداقل ۶۰ ثانیه برای هر تلاش؛ ۹. cancel، timeout، backend error و empty state؛ ۱۰. resize و RTL/LTR.

## اصلاحات انجام‌شده در این مرحله

- `gi.require_version("Gdk", "4.0")` در `eovpn/application.py` اضافه شد.
- `gi.require_version("GdkPixbuf", "2.0")` در `eovpn/eovpn_base.py` اضافه شد.

این اصلاحات فقط warningهای deterministic مربوط به import نسخهٔ GI را حذف می‌کنند و رفتار اتصال شبکه را تغییر نمی‌دهند.

## نتیجه

لایهٔ منطق، resource، schema و تست offline پایدار است. برای تکمیل بررسی ظاهری، باید برنامه در یک session واقعی GTK/Wayland یا X11 اجرا شود؛ نتیجهٔ build یا unit test جایگزین تأیید بصری مالک نیست.
