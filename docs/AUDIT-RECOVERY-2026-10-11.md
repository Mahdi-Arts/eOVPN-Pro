# گزارش ممیزی و احیای کم‌تخریب eOVPN-Pro

تاریخ: ۱۴۰۵/۰۷/۱۹ — دامنه: working tree ریشه؛ checkoutهای `eOVPN-Pro-v2` و `eOVPN-Pro-phase0` فقط برای lineage. `.mimosa` محصول محسوب نشده است.

## ۱. وضعیت فعلی

ریشه پیش از احیا mixed-lineage بود: بخشی از core به phase0 برگشته بود، در حالی که pure modules و candidate v2 قراردادهای جدید را انتظار داشتند. `HEAD` و `origin/master` برابر `64a958c` هستند. نسخهٔ معتبر candidate، `1.5.0` با شناسهٔ `com.github.mahdi-arts.eovpn-pro` است.

## ۲. اصلاح انجام‌شده

- از تغییرات قبل از احیا snapshot قابل‌بازگشت در `/tmp/eovpn-pre-recovery.Qbxx16` تهیه شد.
- فقط فایل‌های tracked و unstagedِ core از `HEAD` هم‌تراز شدند؛ staged و untracked تغییر نکردند.
- ورودی لازم CFFI در `subprojects/networkmanager/cffi_compile.py` در working tree بازگردانده شد تا حذف staged آن build را نشکند؛ index همچنان deletion قبلی را نشان می‌دهد و هیچ reset یا clean انجام نشد.
- warning نوع pointer در NetworkManager با cast صریح اصلاح شد.
- لایهٔ نمایش تست سرعت به یک snapshot مستقل از projection فیلترها منتقل شد؛ فیلتر TCP/UDP، Favorites و Online/Offline دیگر منبع نتایج تست را تغییر نمی‌دهد.
- چیدمان ردیف سرورها با `Gtk.Grid` پایدار شد و کارت ترافیک زنده از layout افقی شکننده به grid responsive منتقل شد.
- auto-connect اکنون دامنهٔ کامل کانفیگ‌ها را مستقل از فیلتر بصری بررسی می‌کند و صف را بر اساس latency مرتب می‌کند. سند هدف اولیه حداقل ۶۰ ثانیه را ذکر می‌کند، اما درخواست صریح بعدی مالک زمان هر تلاش را به ۳۰ ثانیه تغییر داده و کد فعلی همان override را اجرا می‌کند؛ این اختلاف باید در پذیرش نهایی مالک ثبت و تأیید شود.
- About و Settings اطلاعات release، privacy، issue/support، وضعیت backend و راهنمای restart زبان را شفاف‌تر ارائه می‌کنند.
- خطاهای import/activation بک‌اند NetworkManager از مرز CFFI به پیام ساخت‌یافته منتقل می‌شوند و انتخاب صریح بک‌اندِ در دسترس‌نبوده دیگر بی‌صدا به بک‌اند دیگری fallback نمی‌کند.
- زبان فارسی در مسیر action مقدار معتبر را کنترل می‌کند و در صورت نامعتبر یا غیرقابل‌راه‌اندازی بودن launcher، به‌جای خروج ناگهانی پیام قابل‌فهم نشان می‌دهد.
- هر Auto-Connect attempt اکنون `error_code` و `error_message` مستقل دارد؛ Cancel نیز cancellation gate و suppression برای callbackهای دیررس NetworkManager دارد.
- Speed Test دارای cancellation event است؛ در لغو، snapshot قبلی حفظ می‌شود و cascade وابسته به تست متوقف می‌گردد. وضعیت cascade اکنون داخل پنل native اتصال سمت راست نمایش داده می‌شود و دکمهٔ لغو تکراری حذف شده است.
- Reset تنظیمات و کانفیگ‌ها قبل از اجرای عملیات مخرب، confirmation صریح با دکمهٔ پیش‌فرض Cancel نشان می‌دهد.
- Reset اکنون پیش از اجرا یک snapshot محلی با مجوز محدود از کانفیگ‌های مدیریت‌شده و تنظیمات می‌سازد و دکمهٔ `Restore Reset` برای بازگردانی آخرین snapshot دارد؛ credentialهای Secret Service عمداً ذخیره نمی‌شوند و محتوای حساس احتمالی فایل‌های کانفیگ `UNKNOWN` باقی می‌ماند.

## ۳. شواهد اجرایی

| بررسی | نتیجه |
|---|---|
| Python unittest ریشه | `103 passed` |
| metadata parity | PASS، version `1.5.0` |
| scoped `ruff check` | PASS |
| scoped `ruff format --check` | PASS، 44 files |
| `git diff --check` | PASS |
| Meson setup/compile | PASS، `-Dopenvpn3=false` |
| Meson test | PASS، `1/1` |
| desktop-file-validate | PASS |
| GSettings schema / GResource bundle | PASS |
| AppStream strict validation | BLOCKED؛ warning شناسهٔ RDNS دارای hyphen |
| Speed snapshot / cascade regression tests | PASS؛ projection مستقل، صف کامل، timeout حداقل ۶۰ ثانیه، error code/message و cancel gate |
| CFFI contract و artifact ریشه | PASS؛ artifactهای ریشه با خروجی build کنترل‌شده هم‌تراز شدند و نماد `get_last_error` موجود است |
| configured launcher `--help` | PASS؛ build موقت خارج از repository با exit code صفر و نمایش گزینه‌ها اجرا شد |
| native GUI probe | COMPLETED برای startup ایزولهٔ X11؛ اجرای تعاملی کامل ۳۰ سناریو همچنان BLOCKED است |
| cleanup candidate manifest | COMPLETED؛ فقط inventory و rollback ثبت شد؛ هیچ حذف انجام نشد |

## ۴. معماری حفظ‌شده

جریان پیشنهادی و هم‌تراز‌شده:

`eovpn.in → application.py → MainWindow/SettingsWindow → ConnectionManager → NetworkManager/OpenVPN3 → CFFI/C/D-Bus`

pure modules شامل `ConnectionEvent`، cascade، network monitor، speed test، parser، timerها و security utilities حفظ شدند. NetworkManager backend پیش‌فرض است و OpenVPN3 optional باقی می‌ماند.

## ۵. یافته‌های ریشه‌ای

1. اختلاط core قدیمی با pure modules نسخهٔ v2 باعث خطاهای import و شکست ۷ مورد از ۳۱ تست اولیه شد.
2. metadata، application ID، resource prefix و schema بین نسخه‌های `1.33` و `1.5.0` drift کرده بودند.
3. CFFI source deletion در index با Meson contract ناسازگار بود.
4. در وضعیت اصلاح‌شده، archive path checks، اندازهٔ محدود ZIP/folder، HTTPS و timeout، secret handling volatile/Secret Service و modeهای محدود فایل فعال‌اند.

## ۶. حذف مشروط؛ انجام‌نشده

checkoutهای تو‌در‌تو، assets قدیمی `com.github.jkotra.*`، generated binaryهای stale و اسناد فرایندی منسوخ فقط پس از dependency/reference audit، backup و تأیید مالک قابل حذف‌اند. هیچ‌کدام حذف نشده‌اند.

## ۷. وضعیت‌ها

- **COMPLETED:** freeze شواهد، lineage audit، هم‌ترازی حداقلی core، حفظ نتایج speed test هنگام filter، اصلاح layout ردیف/کارت ترافیک، اصلاح scope و timeout auto-connect، بهبود About/Settings، polish بصری Settings، اصلاح parser release notes، اصلاح sorter مدل‌محور GTK، launcher guard، polish بصری GTK/CSS، تست Python، metadata، lint/format، build/test Meson، desktop validation و startup ایزولهٔ X11.
- **BLOCKED:** Codex Deep Security Scan رسمی artifact canonical تحویل نداد و اجرای مجدد آن پس از توقف قبلی انجام نشد؛ `mypy` و `pip-audit` موجود نیستند؛ AppStream strict به warning RDNS متوقف می‌شود؛ اجرای تعاملی کامل GUI و تأیید مالک باقی است؛ بازگردانی Secret Service در Reset عمداً انجام نمی‌شود و نیازمند تصمیم امنیتی/مالک است.
- **UNKNOWN:** OpenVPN3 feasibility در این محیط، تا زمان وجود binding/dependency؛ کیفیت اتصال واقعی و رفتار D-Bus در production؛ پذیرش نهایی timeout ۳۰ ثانیه‌ای در برابر baseline شصت‌ثانیه‌ای سند هدف.
- **OWNER-VERIFIED:** هیچ موردی؛ GUI، import واقعی کانفیگ و اتصال VPN عمداً اجرا نشدند.

## ۸. نتایج Settings، About و language

- Settings اکنون backend انتخاب‌شده، نسخهٔ NetworkManager، plugin OpenVPN، OpenVPN3، CFFI، DCO، Secret Service، زبان و theme را read-only گزارش می‌کند.
- صفحهٔ Backend اکنون capability report ساختاریافته دارد؛ وضعیت‌های تشخیصی با کلیدهای قابل‌تغییر اشتباه نمی‌شوند و DCO فقط در صورت موجودبودن OpenVPN 3 قابل فعال‌سازی است.
- نوار Search/Filters در پنجرهٔ اصلی اکنون با یک Revealer جمع‌شونده است؛ جمع‌کردن صرفاً projection بصری را تغییر می‌دهد و state فیلتر و snapshot سرعت را دست‌کاری نمی‌کند.
- Reset فقط پس از تأیید انجام می‌شود، پیش از آن snapshot محلی با مجوز محدود می‌سازد و `Restore Reset` دارد؛ credentialهای Secret Service در snapshot ذخیره نمی‌شوند.
- About با `Adw.AboutWindow` و fallback GTK شامل version، application ID، سازنده، license، URLهای repository/issue، release notes، privacy، legal، dependency و translator credits است.
- مسیر زبان `en`/`fa` مقدار `GLib.Variant` را اعتبارسنجی می‌کند و launcher ناقص یا restart ناموفق را به پیام قابل‌فهم تبدیل می‌کند.
- رشته‌های جدید About، Speed Test و Reset به فایل‌های ترجمهٔ English/Persian افزوده و با `msgfmt --check` اعتبارسنجی شدند.
- تست آفلاین حالت‌های language variant، مقدار نامعتبر و malformed انجام شد؛ تست GUI/RTL واقعی همچنان BLOCKED است.

## ۹. نتایج امنیتی

- بررسی‌های source-level برای ZIP Slip، symlink/path traversal، duplicate basename، zip bomb، حجم archive/folder، HTTPS/timeout، directiveهای خطرناک OpenVPN، secret handling، file mode، temporary staging، subprocess/xdg-open و عملیات حذف در scope محصول ثبت شده‌اند.
- CFFI شامل `get_last_error` ساختاریافته است؛ pointer ownership و warningهای کامپایل با `-Wall -Wextra -Wpedantic` بررسی شدند و فقط warning pedantic از header خارجی `libnm/nm-dbus-interface.h` مشاهده شد؛ خطای compiler محصولی وجود نداشت.
- `g_printerr` در CFFI backend استفاده نمی‌شود؛ خطاها به مرز Python منتقل می‌شوند.
- Codex Deep Security Scan رسمی پس از توقف قبلی دوباره اجرا نشد و artifact canonical ندارد؛ نتیجهٔ security release gate `BLOCKED` است، نه PASS.
- `pip-audit` و `mypy` در محیط موجود نیستند و بدون نصب dependency جدید `BLOCKED` ثبت شده‌اند.

## ۱۰. نتایج build و test

| Gate | نتیجهٔ زنده |
|---|---|
| unittest | `103 passed` |
| `ruff check eovpn tests` | PASS |
| `ruff format --check eovpn tests` | PASS، 44 فایل |
| `compileall` | PASS |
| metadata parity | PASS، `1.5.0` |
| `git diff --check` | PASS |
| Meson خارج از repository با `-Dopenvpn3=false` | setup/compile PASS |
| Meson test | `1/1` PASS |
| GSettings strict dry-run | PASS |
| GResource dependency check | PASS |
| desktop-file-validate | PASS |
| AppStream | BLOCKED؛ warning `cid-rdns-contains-hyphen` |
| configured launcher `--help` | PASS، exit code صفر |
| OpenVPN3 feasibility | UNKNOWN/BLOCKED؛ binding موجود نیست |

## ۱۱. وضعیت GUI و Owner Acceptance

مرورگر Browser در session جاری هیچ tab یا app ندارد و جایگزین GTK native نیست. اجرای ایزولهٔ X11 با GSettings حافظه‌ای به UI رسید و بدون warning مربوط به ListBox model، Adwaita release notes یا traceback پایان یافت؛ این فقط startup را اثبات می‌کند. ۳۰ سناریوی اجباری GUI، RTL/LTR، resize، منوها، traffic card زنده، speed test گرافیکی و auto-connect واقعی هنوز `BLOCKED` هستند. اتصال VPN، import واقعی کانفیگ، تغییر NetworkManager و D-Bus عمداً اجرا نشدند.

`OWNER-VERIFIED` در این مرحله وجود ندارد.

## ۱۲. فایل‌های قابل حفظ

ماژول‌های pure و domain، تست‌های offline، `speed_state.py`، cascade controller، security utilities، localization، packaging، metadata و CFFI source اصلاح‌شده قابل حفظ‌اند. NetworkManager backend همچنان backend پیش‌فرض و OpenVPN3 optional است.

## ۱۳. فایل‌های نیازمند اصلاح

- generated `.so`های ریشه در یک هم‌ترازی کنترل‌شده با build موقت جایگزین شدند؛ نسخهٔ پیشین در `/tmp/eovpn-cffi-before-20261011-142306` باقی است و حذف نشده است.
- عملیات async لایهٔ CFFI اکنون برای هر worker یک `GMainContext` اختصاصی دارد؛ assertionهای رقابت context که در تلاش‌های واقعی مشاهده شدند مستقیماً هدف‌گیری و artifactهای جدید rebuild شدند. نسخهٔ قبل از این اصلاح در `/tmp/eovpn-cffi-before-context-20261011-143729` باقی است.
- ممیزی compiler با `-Wall -Wextra -Wpedantic` بدون warning محصولی انجام شد؛ تنها warning از header خارجی `nm-dbus-interface.h` و مقدار enum خارج از محدودهٔ ISO C است.
- validation فعلی: metadata، desktop file و GSettings schema موفق؛ AppStream strict با warning شناسهٔ RDNS دارای hyphen و warningهای دسترسی‌ناپذیری URL/screenshot به‌علت DNS محیط، `BLOCKED` باقی ماند. `mypy` و `pip-audit` در PATH موجود نیستند.
- warning AppStream باید با policy هویت برنامه تصمیم‌گیری شود.
- quality gates `mypy`/`pip-audit` و artifact رسمی security scan باید در محیط کنترل‌شده اجرا شوند.
- GUI و Secret Service باید در desktop واقعی بررسی شوند.

## ۱۴. فایل‌های قابل حذفِ مشروط

فقط پس از reference audit و تأیید مالک: checkoutهای `eOVPN-Pro-v2` و `eOVPN-Pro-phase0`، binaryهای generated stale، assetهای `com.github.jkotra.*` در صورت نبود reference، اسناد فرایندی منسوخ و buildهای موقت. هیچ‌یک در این مرحله حذف نشده‌اند.

## ۱۵. جدول وضعیت‌ها

| وضعیت | موارد |
|---|---|
| **COMPLETED** | freeze/lineage audit، اصلاح minimal core، Speed snapshot/filter، ConfigRow/Traffic Card، Auto Connect state/timeout/cancel، Settings diagnostics و capability panel، About و release notes، language guard و launcher، GTK model sorting، polish بصری UI، structured backend errors، offline tests، lint/format/build/metadata gates، cleanup manifest، isolated X11 startup |
| **BLOCKED** | native GUI و ۳۰ سناریوی گرافیکی، Deep Security Scan canonical، `mypy`، `pip-audit`، AppStream strict، rollback credentialهای Secret Service |
| **UNKNOWN** | OpenVPN3، رفتار واقعی D-Bus/NetworkManager، اتصال واقعی، محتوای محرمانهٔ احتمالی فایل‌های backup، generated `.so` ریشه تا rebuild کنترل‌شده، پذیرش نهایی timeout ۳۰ ثانیه‌ای در برابر baseline شصت‌ثانیه‌ای |
| **OWNER-VERIFIED** | هیچ موردی |

## ۱۶. ریسک‌های باقی‌مانده

1. اجرای runtime با binary stale ریشه می‌تواند قرارداد CFFI جدید را نبیند.
2. نبود desktop واقعی مانع اثبات crash-free بودن GUI، RTL و restart زبان است.
3. AppStream warning ممکن است در release policy به خطا تبدیل شود.
4. OpenVPN3 در این محیط قابل feasibility verification نیست.
5. snapshot Reset فایل کانفیگ را با مجوز محدود نگه می‌دارد، اما وجود secret material داخل آن `UNKNOWN` است؛ Secret Service عمداً backup نمی‌شود.

## ۱۷. نقشهٔ راه بعدی

1. بازبینی مالک روی working-tree diff و cleanup manifest.
2. تصمیم دربارهٔ هویت AppStream بدون تغییر شتاب‌زدهٔ application ID.
3. rebuild/install کنترل‌شدهٔ CFFI و حذف stale artifact فقط پس از تأیید.
4. فراهم‌کردن X11/Wayland واقعی و اجرای ۳۰ سناریوی GUI با screenshot/log.
5. اجرای محدود و canonical security scan در محیطی که artifact معتبر تولید کند.
6. اجرای `mypy` و `pip-audit` در محیط کنترل‌شده.
7. تست واقعی import/connect/disconnect فقط با gate و تأیید صریح مالک؛ سپس release packaging.

## ۱۸. فایل‌ها و روش rollback

- گزارش اصلی: `docs/AUDIT-RECOVERY-2026-10-11.md`
- گزارش GUI: `docs/GUI-FUNCTIONAL-TEST-2026-10-11.md`
- manifest پاک‌سازی: `docs/CLEANUP-CANDIDATES-2026-10-11.md`
- backup پیشین احیا: `/tmp/eovpn-pre-recovery.Qbxx16`
- build اعتبارسنجی خارج از repository: `/tmp/eovpn-goal-build.fWpJEb`
- rollback تغییرات working tree باید با patch/backup دقیق و تأیید مالک انجام شود؛ `git reset`، `git clean` و checkout گسترده مجاز نیستند.

این گزارش ادعای موفقیت اتصال VPN، GUI یا تغییر system NetworkManager ندارد.
