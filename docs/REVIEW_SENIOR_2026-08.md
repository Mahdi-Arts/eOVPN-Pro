# 🔍 بازبینی فنی سطح Senior — مخزن eOVPN-Pro

**تاریخ بازبینی:** 2026-08-22 · **شاخه:** `arena/01a028db-eovpn-pro` (کامیت پایه `e76a9e4`)
**نسخه:** 1.5.0 · **مجوز:** GPL-3.0-or-later · **App ID:** `com.github.mahdi-arts.eovpn-pro`
**نقش بازبین:** مهندس Full-Stack ارشد + مدیر سیستم لینوکس ارشد + کارشناس امنیت سایبری
**روش:** خواندن کامل کدبیس (Python + C)، اجرای تست‌ها، اجرای اسکریپت اعتبارسنجی متادیتا، ممیزی بسته‌بندی و مستندات

**اجرای واقعی در محیط بازبینی:**

| بررسی | نتیجه |
|---|---|
| `python3 -m unittest discover -s tests` | ✅ **56/56 OK** |
| `python3 scripts/check_project_meta.py` | ✅ `All metadata checks passed (version 1.5.0)` |
| `python3 -m compileall eovpn tests` | ✅ بدون خطا |
| وجود `.github/workflows/` | ❌ **وجود ندارد** |

---

## ۱. تحلیل معماری و ساختار

### ۱.۱ نمای کلی

| جنبه | وضعیت |
|---|---|
| زبان / UI | Python 3.10+ · GTK4 · Libadwaita |
| لایه بومی | C (CFFI): `eovpn_nm.c` (551 خط، libnm) و `openvpn3.c` (661 خط، D-Bus) |
| سیستم ساخت | Meson ≥ 0.60 + Ninja (+ `meson-python` در `pyproject.toml`) |
| بک‌اندها | NetworkManager (پیش‌فرض) و OpenVPN 3 Linux (اختیاری، `-Dopenvpn3=false`) |
| i18n | gettext — en / fa (RTL) / it / pt_BR |
| تست | unittest — ۵۶ تست آفلاین، همگی پاس |
| حجم کد | ~۵۹۶۳ خط (Python ~۴۷۵۰، C ~۱۲۱۲) |

### ۱.۲ نقاط قوت معماری ✅

1. **انتزاع بک‌اند تمیز:** `ConnectionManager(ABC)` با `connect/disconnect/status/version/start_watch` و دو پیاده‌سازی مستقل. افزودن بک‌اند سوم (مثلاً WireGuard) هزینه معماری پایینی دارد.
2. **جداسازی منطق خالص از UI:** `utils.py`، `auto_connect.py`، `cascade.py`، `speed_test.py` و `ip_lookup/lookup.py` هیچ وابستگی GTK ندارند و دقیقاً به همین دلیل ۵۶ تست آفلاین بدون نشست گرافیکی اجرا می‌شوند. این بهترین تصمیم معماری پروژه است.
3. **مرزبندی لایه بومی:** تعامل با libnm و سرویس openvpn3 در C انجام و از طریق CFFI به پایتون وصل شده — انتخاب درست برای APIهای غیر-GObject.
4. **`CFFIStringMixin` در `backend/_base.py`:** تبدیل رشته CFFI که قبلاً در هر دو بک‌اند تکرار می‌شد، به یک نقطه واحد منتقل شده.
5. **`CascadePhase` (Enum) + توابع خالص در `cascade.py`:** ماشین حالت اتصال آبشاری منطق قابل تست دارد.
6. **`data/eovpn.gresource.xml` با ۲۶۸ ورودی:** UI/CSS/آیکون/پرچم درون یک باندل — نصب تمیز و بدون فایل پراکنده.
7. **مستندسازی دوزبانه در سطح داک‌استرینگ** — بسیار کمیاب و ارزشمند در پروژه‌های متن‌باز.

### ۱.۳ Anti-Pattern ها و ضعف‌های ساختاری ⚠️

| # | مورد | محل | شدت |
|---|---|---|---|
| 1 | **God Object** — `MainWindow` با ۱۷۹۷ خط، ۸۱ متد و **۱۵۴ ارجاع به `_cascade_*`**؛ همزمان ساخت UI، ماشین حالت آبشار، ارکستراسیون تست سرعت، مانیتور شبکه و پردازش رویدادهای D-Bus را انجام می‌دهد. نقض صریح SRP. | `eovpn/main_window.py` | 🔴 بالا |
| 2 | **Service Locator سراسری** — دیکشنری‌های ماژولی `_builder_record`، `_storage_record`، `_session_secrets` با `Base.store()/retrieve()` که `Any` برمی‌گردانند. وضعیت پنهان، تست‌ناپذیری، شکست در سناریوی چند-پنجره. | `eovpn/eovpn_base.py` | 🔴 بالا |
| 3 | **وراثت چندگانه شکننده** — `class MainWindow(Base, Gtk.Builder)` با فراخوانی دستی `Gtk.Builder.__init__(self)` بعد از `super().__init__()`؛ MRO غیرمتعارف و شکننده در برابر تغییر PyGObject. Composition (`self.builder = Gtk.Builder()`) پاسخ درست است. | `main_window.py`, `settings_window.py` | 🟠 متوسط |
| 4 | **وابستگی حلقوی** — `speed_test.parse_ovpn_remote` ایمپورت `parse_ovpn_endpoints` را داخل تابع به تعویق می‌اندازد تا چرخه `speed_test ↔ auto_connect` بشکند. علامت روشن نبود لایه «مدل دامنه». | `eovpn/speed_test.py` | 🟠 متوسط |
| 5 | **کد مرده در ABC** — `ConnectionManager.get_name` هم `@abstractmethod` است و هم بدنه دارد که `self.__NAME__` (نام‌مخدوش‌شده به `_ConnectionManager__NAME__`) را برمی‌گرداند؛ هیچ زیرکلاسی از آن استفاده نمی‌کند. | `connection_manager.py` | 🟡 پایین |
| 6 | **پروب سنگین در ساخت UI** — `_build_backend_tab` صرفاً برای خواندن شماره نسخه، `NetworkManager(None)` و `OpenVPN3(None)` را نمونه‌سازی می‌کند (`callback=None`). باید به یک `staticmethod get_version()` سبک تبدیل شود. | `settings_window.py` | 🟠 متوسط |
| 7 | **`Gio.Settings` تکراری** — `Base.__init__` برای هر نمونه زیرکلاس (MainWindow، SettingsWindow، SettingsSignals، هر ConnectionManager) یک شیء `Gio.Settings` جدید می‌سازد. باید Singleton سطح ماژول باشد. | `eovpn_base.py` | 🟡 پایین |
| 8 | **State سراسری در C** — `static GDBusProxy *UniqueSession = NULL;` در `openvpn3.c`: نه thread-safe است و نه اجازه بیش از یک نشست می‌دهد. | `subprojects/openvpn3/openvpn3.c:40` | 🟠 متوسط |
| 9 | **`GMainLoop` تودرتو** — چهار عملیات NM (`add`/`activate`/`disconnect`/`delete`) هرکدام یک `g_main_loop_new` می‌سازند و از نخ UI اجرا می‌شوند. watchdog ۱۵ ثانیه‌ای (`EOVPN_NM_TIMEOUT_MS`) جلوی هنگ ابدی را می‌گیرد ✅ ولی مسئله **reentrancy** و فریز تا ۱۵ ثانیه باقی است. راه‌حل درست: API آسنکرون libnm + callback. | `eovpn_nm.c:137,260,322,384` | 🟠 متوسط |
| 10 | **دو داستان ساخت موازی** — `pyproject.toml` با `build-backend = "mesonpy"` ادعای wheel می‌کند، در حالی که `meson.build` با `install_subdir('eovpn', install_dir: python_dir)` یک نصب سیستمی انجام می‌دهد. این دوگانگی روزی به تعارض فایل با `pip` منجر خواهد شد. | `pyproject.toml` / `meson.build` | 🟠 متوسط |
| 11 | **هک دستکاری `sys.argv`** — حذف دستی `-c`/`--config` به‌عنوان «سازگاری قدیمی». | `application.py` | 🟡 پایین |
| 12 | **سنتینل رشته‌ای `"null"`** در gschema و `get_setting` — اگر کاربر واقعاً مقدار `null` ذخیره کند، برخورد مقدار رخ می‌دهد. | `gschema.xml` + `eovpn_base.py` | 🟡 پایین |
| 13 | **`otp.blp` و `otp.ui` هر دو کامیت شده** ولی `blueprint-compiler` در زنجیره ساخت نیست → خطر واگرایی خاموش. | `data/ui/` | 🟡 پایین |
| 14 | **APIهای منسوخ GTK4** — `Gtk.MessageDialog`، `Gtk.FileChooserNative`، `Gtk.AboutDialog`، `widget.hide()/show()`، `Gtk.StyleContext.add_provider_for_display`. در GTK 4.10+ deprecated و در GTK5 حذف خواهند شد. جایگزین‌ها: `Adw.MessageDialog`/`Adw.AlertDialog`، `Gtk.FileDialog`، `Adw.AboutWindow`، `set_visible()`. | سراسر UI | 🟠 متوسط |

### ۱.۴ حکم بخش ۱

معماری **بالاتر از میانگین پروژه‌های دسکتاپ متن‌باز** است: لایه‌بندی مشخص، انتزاع بک‌اند درست و هسته منطقی تست‌پذیر. اما دو بدهی فنی جدی — `MainWindow` ۱۷۹۷ خطی و Service-Locator سراسری — سقف توسعه‌پذیری را پایین نگه داشته‌اند. جالب اینکه خودِ `docs/ARCHITECTURE.md` مورد دوم را به‌عنوان «کار آینده» پذیرفته است؛ این صداقت مهندسی ارزشمند است ولی جای رفع مشکل را نمی‌گیرد.

---

## ۲. بررسی کیفیت کد

### ۲.۱ نقاط قوت ✅

- **تایپ‌هینت مدرن و پیوسته:** `str | None`، `dict[str, float]`، `frozenset[str]`، `Callable`، `from __future__ import annotations`.
- **مدیریت خطای منسجم:** تقریباً تمام مسیرهای I/O و D-Bus در `try/except` با logging سطح‌بندی‌شده (`logger.debug/info/warning/error`) هستند — نه `print`.
- **۵۶ تست واحد معنادار:** Zip-Slip، zip-bomb، رد HTTPS، پارس پروتکل TCP/UDP، تایم‌اوت تطبیقی (کف/سقف)، صف آبشاری، فیلتر سرور، lookup با mock، و smoke-import.
- **تجزیه `setup()`:** در هر دو پنجره به متدهای `_build_*` شکسته شده — پیشرفت واضح نسبت به گزارش‌های قبلی.
- **کد C تمیز:** استفاده از `g_autoptr`، بررسی `GError` در همه نقاط، `g_free`/`g_object_unref` منظم، هدر GPL روی هر دو فایل، `.clang-format` (سبک GNU).
- **ابزار کیفیت پیکربندی‌شده:** ruff (`E,W,F,I,N,UP,SIM`)، mypy (`check_untyped_defs = true`)، `.editorconfig`.

### ۲.۲ نقض‌های Clean Code / SOLID / DRY / KISS

**SRP (S در SOLID) — نقض شدید**
`MainWindow` حداقل ۵ مسئولیت مجزا دارد. باید به این‌ها شکسته شود: `MainWindowView` (ویجت)، `CascadeController` (ماشین حالت — ۱۵۴ ارجاع `_cascade_*` که در ~۱۵ attribute پخش شده‌اند)، `NetworkMonitor` (خواندن `/proc/net/dev`)، `SpeedTestController`، `ConnectionEventHandler`.

**DRY — چند نقض مشخص**
1. `Settings.all_settings` عملاً همان ثابت‌های کلاس را به‌صورت رشته‌های خام تکرار می‌کند. تنها محافظ فعلی `scripts/check_project_meta.py` است — یعنی «تست به‌جای طراحی». راه درست: تولید لیست از روی `__dict__` کلاس یا استفاده از یک `Enum`.
2. سه متد اعلان (`send_connected_notification` / `send_disconnected_notification` / `send_error_notification`) تقریباً یکسان‌اند.
3. دو پارسر `.ovpn`: `speed_test.parse_ovpn_remote` و `auto_connect.parse_ovpn_endpoints`.
4. **دو پیکربندی لینتر موازی:** `.flake8` (`max-line-length = 110`) و `[tool.ruff]` (`line-length = 110`) — هر دو در `requirements-dev.txt` نصب می‌شوند و در `CONTRIBUTING.md`/`RELEASE_CHECKLIST.md` هر دو فراخوانی شده‌اند. ruff عملاً جانشین flake8 است؛ نگهداری هر دو هزینه بی‌دلیل و ریسک واگرایی قواعد است.

**OCP / DIP**
افزودن یک بک‌اند جدید تمیز است ✅ ولی UI مستقیماً به `retrieve("CM").get("instance")` (رشته جادویی) وابسته است — نه به یک اینترفیس تزریق‌شده. این نقض DIP است.

**KISS**
- بازتعریف closureهای `format_speed`/`format_size` داخل `update_network_speed` — این تابع **هر ثانیه** اجرا می‌شود.
- `update_network_speed` دو بار روی کل `/proc/net/dev` حلقه می‌زند (یک‌بار برای اینترفیس‌های VPN، یک‌بار fallback) — یک عبور کافی است.
- منطق `on_connection_event` با `if type(result) is list` نوع‌محور شاخه می‌زند (باید `isinstance` باشد و بهتر: یک نوع رویداد صریح).

**پیچیدگی شناختی**
`on_connection_event` و `_finish_cascade` هرکدام بیش از ۸ شاخه تودرتو دارند و ترکیب چند سطح از حالت (`_cascade_active`، `was_connected`، `manual_disconnect`، `should_reconnect`) را همزمان می‌سنجند. اینها بالاترین پیچیدگی شناختی پروژه‌اند و اولین کاندید بازآرایی هستند.

**باگ‌های ریز/ناسازگاری‌ها**
- `requirements.txt` **بدون newline پایانی** تمام می‌شود و بلوک کامنت آخر آن (متعلق به فایل dev) ناقص چسبیده است.
- `ip_lookup/lookup.py`: داک‌استرینگ `ip_api_https()` می‌گوید ip-api.com ولی کد `api.ipify.org` را صدا می‌زند — مستند غلط.
- ایمپورت‌های ناهمگون: `dialogs/otp.py` و `backend/openvpn3/dbus.py` مطلق (`from eovpn...`)، بقیه نسبی.
- `po/LINGUAS` شامل `en it pt_BR fa` است ولی منوی زبان در `main_window.py` فقط English و فارسی را نشان می‌دهد → **ترجمه‌های it و pt_BR از UI غیرقابل دسترسی‌اند** (۳۱ و ۴۷ رشته کار ترجمه‌شده بلااستفاده).
- `debian/rules`: `override_dh_auto_install` فقط `dh_auto_install` را صدا می‌زند — override بی‌اثر.

### ۲.۳ حکم بخش ۲

کد **خوانا، تایپ‌شده، لاگ‌دار و تست‌شده** است — بسیار بهتر از میانگین. مانع اصلی، تمرکز حجم در دو فایل و چند نقض DRY ساختاری است، نه سبک کدنویسی.

---

## ۳. بررسی امنیت و شبکه

> پروژه یک اپلیکیشن دسکتاپ است، پس OWASP Top 10 وب مستقیماً اعمال نمی‌شود. مدل تهدید درست اینجا: **زنجیره تأمین کانفیگ VPN (untrusted input)**، **مدیریت راز**، **مرز D-Bus/سیستم**، و **امنیت زنجیره ساخت**.

### ۳.۱ کنترل‌های امنیتی موجود و تأییدشده ✅

| کنترل | پیاده‌سازی | تأیید |
|---|---|---|
| Zip-Slip | `is_safe_path()` با `os.path.commonpath` | ✅ + تست واحد |
| Zip-Bomb | `MAX_ZIP_DOWNLOAD_BYTES` = 64 MiB، `MAX_EXTRACTED_TOTAL_BYTES` = 256 MiB، `MAX_ZIP_ENTRIES` = 20000 | ✅ + تست واحد |
| فقط HTTPS | `_SafeRedirectHandler` ریدایرکت غیر-HTTPS را مسدود می‌کند | ✅ + تست واحد |
| استخراج امن | `O_NOFOLLOW` + مجوز `0600`، رد symlink، رد basename تکراری | ✅ |
| ممیزی کانفیگ | `audit_ovpn_content()` روی `DANGEROUS_OVPN_DIRECTIVES` (`up`, `down`, `script-security`, …) | ✅ |
| راز agent-owned | `NM_SETTING_SECRET_FLAG_AGENT_OWNED` و **abort در صورت شکست** | ✅ (`eovpn_nm.c`) |
| مالکیت پروفایل | تگ `managed-by=eovpn-pro` روی پروفایل‌های NM | ✅ |
| watchdog | `EOVPN_NM_TIMEOUT_MS` / `EOVPN_DBUS_TIMEOUT_MS` = ۱۵۰۰۰ms روی همه فراخوانی‌های سنکرون | ✅ |
| عدم لاگ OTP | در `send_otp` صریحاً کامنت و رعایت شده | ✅ |
| رمز روی دیسک | هرگز در dconf/gschema — Secret Service + RAM موقت | ✅ |
| فایل موقت | `tempfile.mkstemp()` (۰۶۰۰ ذاتی) + `os.chmod(0o600)` صریح + حذف در `finally` | ✅ |

این سطح از سخت‌سازی برای یک پروژه شخصی **قابل‌توجه** است.

### ۳.۲ آسیب‌پذیری‌ها و ریسک‌های باقی‌مانده

**🔴 P0-1 — اجرای handler روی محتوای غیرقابل‌اعتماد (`eovpn_base.py:134`)**
```python
self.edit_button.connect("clicked", lambda w: subprocess.Popen(["xdg-open", str(target_file)]))
```
`target_file` از نام فایل درون ZIP دانلودشده می‌آید. اگرچه استخراج، basename را مسطح می‌کند و `shell=False` است (پس تزریق فرمان مستقیم نداریم)، اما:
- هیچ بررسی وجود فایل یا محدودسازی به دایرکتوری کانفیگ انجام نمی‌شود؛
- پسوند فایل کنترل نمی‌شود → یک آرشیو مخرب می‌تواند `payload.desktop` یا `x.html` بسازد و `xdg-open` handler دلخواه سیستم را اجرا کند.
**رفع:** اجبار پسوند `.ovpn`، اعتبارسنجی `Path.resolve()` داخل `EOVPN_CONFIG_DIR/CONFIGS`، بررسی `is_file()`، و ترجیحاً استفاده از `Gtk.FileLauncher`/`Gio.AppInfo` به‌جای `Popen`.

**🟠 P1-1 — تناقض مستندات/رفتار در «حذف همه اتصالات»**
پیاده‌سازی C در واقع **درست** است: `delete_all_vpn_connections()` فقط روی `eovpn_connection_is_managed(conn)` حلقه می‌زند ✅. اما متن دیالوگ تأیید در `settings_window.py:460` می‌گوید:
> "This will permanently remove **ALL** VPN profiles from NetworkManager, **including profiles created by other applications**."
این متن **غلط و ترسناک** است و کاربر را از یک عملیات ایمن می‌ترساند (یا بدتر: به او یاد می‌دهد به متن دیالوگ‌های امنیتی اعتماد نکند). باید اصلاح شود.

**🟠 P1-2 — فایل موقت حاوی کلید خصوصی در `/tmp` سراسری**
`connection_manager.py:210`: `tempfile.mkstemp(suffix=".ovpn", text=True)` بدون آرگومان `dir=`. کل کانفیگ + گواهی CA (و در بسیاری از کانفیگ‌ها `<key>` inline) در `/tmp` نوشته می‌شود. مجوز ۰۶۰۰ است ✅ ولی روی سیستم‌های بدون `fs.protected_regular`/`/tmp` جداگانه، مسیر قابل مشاهده است و در برابر symlink-race و بازیابی پس از crash آسیب‌پذیرتر است.
**رفع:** `dir=self.EOVPN_CONFIG_DIR` (زیر `$XDG_CONFIG_HOME`، مالکیت کاربر) یا `$XDG_RUNTIME_DIR` (tmpfs، پاک‌شونده با logout). `$XDG_RUNTIME_DIR` گزینه ایده‌آل است.

**🟠 P1-3 — نوشتن روی Keyring در هر ضربه کلید**
`process_password` به سیگنال تغییر متن `Gtk.PasswordEntry` وصل است و برای **هر کاراکتر** یک `Secret.password_store` صادر می‌کند. نتیجه: ده‌ها نسخه ناقص رمز در Secret Service، فشار بی‌دلیل روی D-Bus، و افزایش سطح حمله. باید به `activate`/`focus-out` یا یک debounce منتقل شود.

**🟡 P2-1 — SSRF نرم**
`is_private_or_loopback_host()` فقط **هشدار** می‌دهد و مسدود نمی‌کند. ریسک واقعی پایین است (URL توسط خود کاربر وارد می‌شود) ولی برای دفاع در عمق باید حداقل تأیید صریح بگیرد.

**🟡 P2-2 — Fallback رمز به حافظه سراسری**
`_session_secrets` یک `dict` سطح ماژول است. رمز در heap پایتون بدون امکان `mlock` یا صفرکردن قطعی می‌ماند. برای یک اپ دسکتاپ قابل قبول است ولی باید حداقل هنگام disconnect پاک شود.

**🟡 P2-3 — بدون CVE-scan فعال**
`pip-audit` در `requirements-dev.txt` و `RELEASE_CHECKLIST.md` هست ولی **هیچ‌جا به‌صورت خودکار اجرا نمی‌شود** (چون CI وجود ندارد). Dependabot پیکربندی شده ✅ ولی اکوسیستم `github-actions` آن روی مخزنی که workflow ندارد بلااستفاده است.
سطح حمله وابستگی‌ها خوشبختانه کوچک است: فقط `cffi>=1.15.0` و `PyGObject>=3.42.0`. هیچ CVE فعال شناخته‌شده‌ای در این دو پین باز دیده نمی‌شود، اما پین‌های `>=` بدون lockfile یعنی build غیرقابل بازتولید.

**🟡 P2-4 — ریسک امنیت زنجیره تأمین در Flatpak**
مانیفست `dist/flatpak/*.yml` منابعی را با **tag گیت** می‌آورد (`NetworkManager 1.38.2`، `openvpn3-linux v24.1`، `eudev v3.2.10`، `protobuf v34.1`، …) نه با `commit` sha. تگ‌های گیت قابل جابه‌جایی‌اند → build غیرقابل بازتولید و مسیر بالقوه حمله زنجیره تأمین. آرشیوهای tarball درست پین شده‌اند (`sha256` ✅) ولی منابع `type: git` نه. ضمناً `NetworkManager 1.38.2` (۲۰۲۲) بسیار قدیمی است و `-Ddbus_policy_dir=/tmp` در ماژول openvpn3 یک هک ناخوشایند است.

**🟡 P2-5 — بدون امضای بسته**
هیچ امضای GPG برای `.deb`/`.rpm` و هیچ تولید/انتشار `SHA256SUMS` عملی وجود ندارد (فقط در مستندات ادعا شده).

### ۳.۳ امنیت لایه شبکه

- HTTPS اجباری ✅، ولی **بدون certificate pinning** و بدون اجبار حداقل TLS 1.2 روی `ssl.SSLContext` سفارشی — به پیش‌فرض سیستم متکی است (قابل قبول، اما برای اپ VPN می‌شد سخت‌گیرتر بود).
- `REQUEST_TIMEOUT = 3.5s` در lookup و fallback سه‌گانه ارائه‌دهنده ✅ — منطقی.
- `speed_test.ping_host` عمداً `ConnectionRefusedError` را «زنده» تلقی می‌کند (میزبان پاسخ داد ⇒ RTT معتبر) — تصمیم درست و مستند‌شده ✅.
- **بدون kill-switch / DNS-leak protection.** برای اپلیکیشنی که خود را «Pro VPN client» معرفی می‌کند، نبود گزینه kill-switch یک شکاف کارکردی-امنیتی است، نه صرفاً یک feature غایب. کاربری که تصور می‌کند ترافیکش محافظت شده، هنگام قطع تونل بی‌محافظت می‌ماند.

### ۳.۴ حکم بخش ۳

پایه امنیتی **قوی و طراحی‌شده** است (نه وصله‌ای). چهار مورد قابل اقدام باقی مانده که هیچ‌کدام critical نیستند: `xdg-open` بدون اعتبارسنجی، فایل موقت در `/tmp` سراسری، نوشتن Keyring در هر کلید، و متن گمراه‌کننده دیالوگ حذف. مهم‌ترین شکاف واقعی، **نبود اجرای خودکار `pip-audit`/CodeQL** است.

---

## ۴. ارزیابی مستندات

### ۴.۱ کمیت و پوشش ✅

مجموعه مستندات از نظر گستردگی در سطح پروژه‌های سازمانی است:

| فایل | ارزیابی |
|---|---|
| `README.md` | دوزبانه، badgeدار، ۴ روش نصب، جدول مستندات، مشخصات پروژه — عالی |
| `PACKAGING.md` (۲۰۸ خط) | .deb / .rpm / Flatpak / Arch با دستورهای دقیق و پیش‌نیازها — بسیار خوب |
| `docs/RELEASE_CHECKLIST.md` | runbook قابل اجرا و چک‌لیستی — بسیار خوب |
| `docs/ARCHITECTURE.md` | نمودار لایه‌ها، تصمیم‌های طراحی، جدول ماژول‌ها — خوب |
| `SECURITY.md` | policy + کانال گزارش + یادداشت‌های طراحی امنیتی — خوب |
| `CONTRIBUTING.md` | quick-start قابل کپی-پیست — خوب |
| `CHANGELOG.md` | فرمت Keep a Changelog با بخش Unreleased — خوب |
| `eovpn.1` | صفحه man موجود ✅ (نادر در پروژه‌های مشابه) |
| داک‌استرینگ‌ها | دوزبانه و در تقریباً همه توابع عمومی — عالی |

### ۴.۲ مشکل اصلی: 🔴 شکاف مستندات ↔ واقعیت

این جدی‌ترین ایراد بخش مستندات است — مستندات چیزهایی را ادعا می‌کنند که **روی دیسک وجود ندارند**:

| ادعا | محل | واقعیت |
|---|---|---|
| badge CI به `ci.yml` | `README.md:11` | ❌ فایل وجود ندارد → badge خراب/unknown |
| «این بررسی‌ها خودکار در `.github/workflows/ci.yml` اجرا می‌شوند» | `README.md:144` | ❌ اجرا نمی‌شوند |
| «`release.yml` روی تگ‌ها بسته منتشر می‌کند» | `README.md:145` | ❌ وجود ندارد |
| «مخزن **دو وورک‌فلو فعال** دارد» | `PACKAGING.md:165-171` | ❌ صفر وورک‌فلو |
| «`pip-audit` روی هر push اجرا می‌شود» | `SECURITY.md:54` | ❌ اجرا نمی‌شود |
| «`.github/workflows/ci-cd.yml` (جدید)» + «`dist/ci/ci-cd.yml` حذف شد» | `QA_REPORT.md:156-158` | ❌ اولی ساخته نشد؛ دومی واقعاً حذف شد → **الان هیچ workflow ای در مخزن نیست** |
| «CI/CD فعال (.deb + Flatpak)» | `debian/changelog` نسخه 1.5.0 | ❌ |
| CI/release workflow در Unreleased | `CHANGELOG.md:10-12` | ❌ |

از نظر امنیتی این صرفاً «مستند قدیمی» نیست: `SECURITY.md` به کاربر و مشارکت‌کننده اطمینان می‌دهد که اسکن CVE خودکار انجام می‌شود، در حالی که انجام نمی‌شود. این یک **ادعای امنیتی نادرست** است و باید یا کد پشتیبانش ساخته شود یا ادعا حذف گردد.

### ۴.۳ سایر ایرادهای مستندات

- `docs/ANALYSIS.md`، `docs/REVIEW.md` و `QA_REPORT.md` سه گزارش بازبینی با تاریخ یکسان، کامیت‌های متفاوت (`710d13d`، `3b2330c`) و امتیازهای متناقض (۶.۸، ۸.۹، …) هستند که هیچ‌کدام با کامیت فعلی مطابقت ندارند. اینها **artifact** فرآیندند، نه مستند محصول؛ باید بایگانی یا در یک فایل واحد ادغام شوند.
- `PACKAGING.md` بخش ۴ آموزش `PKGBUILD` می‌دهد اما **هیچ `PKGBUILD` ای در مخزن نیست** — کاربر Arch باید آن را از روی مستند کپی و دستی بسازد.
- تاریخ‌های `debian/changelog` و `%changelog` اسپک: `Sat, 22 Aug 2026` — تاریخ آینده نسبت به بیشتر ابزارها؛ `lintian` روی این حساس است.
- داک‌استرینگ `ip_api_https()` منبع اشتباه ذکر می‌کند.
- `data/ui/README.md` و `data/icons/README.md` وجود دارند ✅ (نکته مثبت).
- کلاً هیچ مستند API/داخلی تولیدشده (Sphinx/pdoc) وجود ندارد — برای اپ دسکتاپ ضروری نیست.

### ۴.۴ حکم بخش ۴

از نظر **کیفیت نگارش و پوشش**، مستندات ۹/۱۰ هستند. از نظر **صحت**، به‌خاطر هشت ادعای نادرست درباره CI/CD و بسته Arch، نمره جدی از دست می‌دهند. مستند نادرست از مستند ناقص بدتر است.

---

## ۵. ارزیابی انتشار و بسته‌بندی

### ۵.۱ وضعیت به تفکیک فرمت

| فرمت | فایل‌ها | وضعیت | ارزیابی |
|---|---|---|---|
| **`.deb`** | `debian/{control,rules,changelog,copyright,postinst,postrm,source/format}` + `scripts/build-deb.sh` | 🟢 **آماده** | `debhelper-compat 13`، `dh --buildsystem=meson`، `-Dopenvpn3=false`، Depends کامل و درست (gir1.2-*، network-manager-openvpn)، `Standards-Version: 4.6.2` |
| **`.rpm`** | `dist/rpm/eovpn-pro.spec` | 🟢 **آماده** | کامل‌ترین بسته پروژه: `%meson`/`%meson_build`/`%meson_install`، `%find_lang`، `%check` با `desktop-file-validate` و `appstreamcli`، file-trigger برای icon-cache، `%license`/`%doc` درست |
| **Flatpak** | `dist/flatpak/*.yml` + ۲ patch + `python3-cffi.json` + `scripts/build-flatpak.sh` | 🟡 **کار می‌کند ولی شکننده** | runtime `org.gnome.{Sdk,Platform}//50`، finish-args دقیق و کم‌مجوز ✅. اما کل NetworkManager + openvpn3-linux + protobuf + eudev داخل باندل کامپایل می‌شود → build بسیار طولانی، NM نسخه 1.38.2 (۲۰۲۲)، منابع git بدون پین commit |
| **AppImage** | `dist/appimage/build-appimage.sh` | 🟠 **اسکلت آزمایشی** | اسکریپت درست است (Meson→AppDir، کپی desktop/icon، `glib-compile-schemas`) ولی به `linuxdeploy` خارجی متکی است و اگر نباشد فقط AppDir می‌سازد. خودِ `PACKAGING.md` صادقانه آن را «not production-ready» می‌نامد ✅ |
| **`.pkg.tar.zst` (Arch)** | — | 🔴 **وجود ندارد** | فقط snippet در `PACKAGING.md`؛ هیچ فایل `PKGBUILD` در مخزن نیست، در حالی که README/PACKAGING پشتیبانی Arch را تبلیغ می‌کنند |

### ۵.۲ 🔴 نبود کامل CI/CD — بحرانی‌ترین یافته کل بازبینی

```
.github/
├── FUNDING.yml
├── dependabot.yml
└── ISSUE_TEMPLATE/{bug_report.yml, config.yml, feature_request.yml}
```
**هیچ دایرکتوری `workflows/` وجود ندارد. صفر workflow.**

پیامدها:
1. badge CI در README شکسته است (اولین چیزی که یک بازدیدکننده می‌بیند).
2. ۵۶ تست موجود روی هیچ PR ای اجرا نمی‌شوند — اگرچه `meson.build` هوشمندانه `test('unit', …, ['-m','unittest','discover','-s','tests','-v'])` را ثبت کرده و `meson test` کار می‌کند ✅، هیچ‌کس آن را صدا نمی‌زند.
3. `scripts/check_project_meta.py` **کاملاً CI-ready** است (exit code غیرصفر، پیام واضح) ولی هیچ‌جا اجرا نمی‌شود.
4. هیچ بسته‌ای به‌صورت خودکار تولید یا به Release پیوست نمی‌شود؛ انتشار کاملاً دستی است.
5. `dependabot.yml` بخش `github-actions` دارد که روی مخزن بدون workflow بی‌اثر است.
6. هیچ اسکن امنیتی (pip-audit / CodeQL) اجرا نمی‌شود.

نکته تلخ: زیرساخت کیفیت **آماده است** (تست‌ها، اسکریپت متادیتا، هدف meson test، اسکریپت‌های build) و فقط ۱۵۰ خط YAML بین وضعیت فعلی و یک خط لوله کامل فاصله است.

### ۵.۳ ناسازگاری‌های بسته‌بندی

1. `debian/rules`: `export PYBUILD_NAME = eovpn` تعریف شده ولی buildsystem مسون است، نه pybuild → متغیر بی‌اثر و گمراه‌کننده.
2. `debian/rules`: `override_dh_auto_install` بی‌اثر (فقط `dh_auto_install`) → باید حذف شود.
3. `debian/control`: `dh-python` در `Build-Depends` نیست، در حالی که `scripts/build-deb.sh` و `PACKAGING.md` آن را نصب می‌کنند → یا اضافه شود یا از مستندات حذف گردد.
4. `pyproject.toml` با `mesonpy` ادعای بسته PyPI دارد ولی `meson.build` نصب سیستمی می‌کند (`install_subdir` به `python_dir`) → دو مسیر متعارض. `twine` هم در `requirements-dev.txt` هست بدون اینکه انتشاری روی PyPI برنامه‌ریزی شده باشد.
5. تاریخ‌های changelog در آینده (2026-08-22) — `lintian` روی این هشدار می‌دهد.
6. `.gitignore` خط `tests/data/**` را نادیده می‌گیرد — اگر روزی fixture واقعی نیاز شود، سکوت‌وار حذف خواهد شد.
7. هیچ `SHA256SUMS` یا امضای GPG در فرآیند انتشار.

### ۵.۴ حکم بخش ۵

**فایل‌های بسته‌بندی خوب و حرفه‌ای نوشته شده‌اند** (اسپک RPM واقعاً نمونه است)، اما **اتوماسیون صفر** است و **یک فرمت وعده‌داده‌شده (Arch) اصلاً وجود ندارد**. فاصله تا «آماده انتشار» کم است ولی این فاصله دقیقاً همان‌جایی است که خطای انسانی رخ می‌دهد.

---

## ۶. امتیازدهی کمی

| معیار | امتیاز | توجیه فشرده |
|---|:---:|---|
| **کیفیت کد و معماری** | **7 / 10** | لایه‌بندی درست، تایپ‌هینت کامل، ۵۶ تست پاس، انتزاع بک‌اند تمیز؛ اما `MainWindow` ۱۷۹۷ خطی، Service-Locator سراسری، وابستگی حلقوی و APIهای منسوخ GTK |
| **امنیت** | **7 / 10** | سخت‌سازی واقعی و طراحی‌شده (Zip-Slip، zip-bomb، HTTPS-only، agent-owned secrets، watchdog، ممیزی کانفیگ)؛ اما `xdg-open` بدون اعتبارسنجی، `/tmp` سراسری برای کانفیگ حاوی کلید، Keyring-write در هر کلید، صفر اسکن خودکار CVE، نبود kill-switch |
| **مستندات** | **6.5 / 10** | پوشش و نگارش دوزبانه در سطح سازمانی؛ اما هشت ادعای نادرست درباره CI/CD و بسته Arch، و سه گزارش بازبینی متناقض و منسوخ |
| **قابلیت توسعه (Scalability)** | **6 / 10** | افزودن بک‌اند آسان است ✅؛ اما وضعیت سراسری تک‌نمونه‌ای، `static UniqueSession` در C، `GMainLoop` تودرتوی سنکرون و god-object مانع رشد امن کدبیس‌اند |
| **آمادگی بسته‌بندی** | **6 / 10** | .deb و .rpm واقعاً آماده؛ Flatpak شکننده؛ AppImage اسکلت؛ **Arch غایب**؛ **CI/CD کاملاً غایب** با وجود ادعای مستندات |

### 🎯 امتیاز کلی: **6.5 / 10**

> (7 + 7 + 6.5 + 6 + 6) ÷ 5 = **6.5**

**تفسیر:** پروژه‌ای **جدی، امنیت‌محور و خوش‌ساخت** با یک شکاف واحد و بزرگ: فاصله میان آنچه مستندات ادعا می‌کنند و آنچه در مخزن هست. بستن این شکاف (عمدتاً CI/CD + PKGBUILD + تصحیح مستندات) به‌تنهایی امتیاز کلی را به محدوده **۸+** می‌برد، بدون اینکه یک خط منطق تجاری تغییر کند.

> تفاوت با امتیاز ۸.۹ ادعاشده در `QA_REPORT.md`: آن گزارش فرض کرده CI فعال شده است. تأیید مستقیم روی دیسک نشان می‌دهد `.github/workflows/` وجود ندارد و `dist/ci/` هم حذف شده — یعنی اکنون **هیچ تعریف خط لوله‌ای در مخزن باقی نمانده**.

---

## ۷. طرح اجرایی (Action Plan for Prompt 2) ⚠️ **بسیار مهم**

> این فهرست به ترتیب اولویت مرتب شده است. هر آیتم فایل دقیق، نوع عملیات (ایجاد/ویرایش/حذف) و معیار پذیرش دارد.

### 🔴 فاز P0 — بستن شکاف «ادعا در برابر واقعیت» (بحرانی)

**1. ایجاد `.github/workflows/ci.yml`** *(فایل جدید)*
- Triggerها: `push` روی `master` و `arena/**`، `pull_request`، `workflow_dispatch`.
- Job `lint-and-test` (ubuntu-latest، matrix پایتون `3.10`/`3.11`/`3.12`):
  `pip install -r requirements-dev.txt` → `ruff check .` → `mypy --ignore-missing-imports eovpn tests` → `python3 -m unittest discover -s tests -v` → `python3 scripts/check_project_meta.py` → `python3 -m compileall -q eovpn tests`.
- Job `security`: `pip-audit -r requirements.txt` + `github/codeql-action` برای `python` و `cpp`.
- Job `build-meson`: نصب `meson ninja-build libnm-dev libgtk-4-dev libadwaita-1-dev libsecret-1-dev libnotify-dev gettext desktop-file-utils appstream` → `meson setup build -Dopenvpn3=false` → `ninja -C build` → `meson test -C build` → `desktop-file-validate` → `appstreamcli validate --no-net`.
- Job `build-deb`: اجرای `scripts/build-deb.sh` و آپلود artifact.
- Job `build-flatpak`: `flatpak/flatpak-github-actions/flatpak-builder@v6` با `continue-on-error: true` (به‌دلیل زمان build طولانی NM/openvpn3).

**2. ایجاد `.github/workflows/release.yml`** *(فایل جدید)*
- Trigger: `push` روی تگ `v*.*.*` + `workflow_dispatch`.
- ساخت `.deb`، `.rpm` (در کانتینر `fedora:latest` با `rpmbuild`)، و `.pkg.tar.zst` (کانتینر `archlinux:base-devel` با `makepkg`).
- تولید `SHA256SUMS` برای همه artifactها.
- `softprops/action-gh-release` با پیوست همه بسته‌ها + `SHA256SUMS` و بدنه از `CHANGELOG.md`.
- تنظیم `permissions: contents: write` و pin کردن همه actionها به SHA کامیت (نه tag).

**3. ایجاد `PKGBUILD`** *(فایل جدید، ریشه مخزن یا `dist/arch/PKGBUILD`)*
- `pkgname=eovpn-pro`، `pkgver=1.5.0`، `arch=('x86_64')`، `license=('GPL3')`.
- `depends`: `python-gobject gtk4 libadwaita libsecret libnotify networkmanager networkmanager-openvpn openvpn python-cffi`.
- `makedepends`: `meson ninja gettext appstream-glib`.
- `build()`: `arch-meson . build -Dopenvpn3=false && meson compile -C build`
- `check()`: `meson test -C build`
- `package()`: `meson install -C build --destdir "$pkgdir"`
- سپس `dist/arch/.SRCINFO` تولید شود.

**4. ویرایش `README.md`**
- URL badge CI را به workflow واقعاً موجود اصلاح کنید.
- خطوط ۱۴۴–۱۴۷: پس از ساخت workflowها، ادعا صحیح می‌شود — متن را با نام فایل‌های واقعی هماهنگ کنید.
- بخش نصب: افزودن روش Arch/`PKGBUILD` با فرمان `makepkg -si`.
- badgeهای اضافه: نسخه، مجوز، پایتون.

**5. ویرایش `PACKAGING.md`**
- بخش ۵: بازنویسی بر اساس `ci.yml` و `release.yml` واقعی و افزودن job سه‌گانه `.deb`/`.rpm`/`.pkg.tar.zst`.
- بخش ۴: ارجاع به فایل `PKGBUILD` واقعی به‌جای snippet درون‌متنی.

**6. ویرایش `SECURITY.md`**
- خط ۵۴: ادعای «`pip-audit` روی هر push» فقط پس از افزوده‌شدن job `security` معتبر است — همزمان با آیتم ۱ نگه دارید؛ در غیر این صورت حذف کنید.
- افزودن بخش «Supply-chain» شامل پین‌شدن actionها به SHA و پین‌شدن منابع Flatpak.

**7. ویرایش `CHANGELOG.md` و `debian/changelog`**
- بخش `[Unreleased]`: ادعای workflow را به واقعیت پس از پیاده‌سازی هماهنگ کنید.
- `debian/changelog`: حذف عبارت «an active CI/CD workflow» یا اصلاح آن؛ **تصحیح تاریخ آینده** `Sat, 22 Aug 2026` به تاریخ معتبر.
- `dist/rpm/eovpn-pro.spec` بخش `%changelog`: همان تصحیح تاریخ.

---

### 🟠 فاز P1 — رفع امنیتی و پایداری

**8. ویرایش `eovpn/eovpn_base.py` (حدود خط ۱۳۴) — سخت‌سازی دکمه ویرایش**
- ساخت متد `_open_config_in_editor(self, target_file: Path)` به‌جای lambda.
- اعتبارسنجی: `resolved = target_file.resolve()`؛ بررسی `resolved.is_file()`؛ بررسی `resolved.suffix.lower() == ".ovpn"`؛ بررسی اینکه `resolved` واقعاً زیر `Path(self.ovpn_dir).resolve()` باشد (`is_relative_to`).
- در صورت شکست هر شرط: log + toast خطا و **عدم اجرا**.
- جایگزینی `subprocess.Popen(["xdg-open", …])` با `Gtk.FileLauncher(file=Gio.File.new_for_path(...)).launch()`.

**9. ویرایش `eovpn/connection_manager.py` (حدود خط ۲۱۰) — فایل موقت امن**
- `tempfile.mkstemp(suffix=".ovpn", dir=self._secure_tmp_dir())`.
- افزودن هلپر `_secure_tmp_dir()` که به ترتیب `$XDG_RUNTIME_DIR` → `EOVPN_CONFIG_DIR` → `/tmp` را امتحان می‌کند.
- تضمین حذف فایل حتی در مسیرهای استثنایی (بلوک `finally` موجود را بازبینی کنید) و در صورت امکان بازنویسی محتوا با صفر پیش از `unlink`.

**10. ویرایش `eovpn/settings_window.py` (خطوط ۴۵۵–۴۶۸) — تصحیح متن دیالوگ**
- متن فعلی غلط است. جایگزین: «همه پروفایل‌های VPN که **توسط eOVPN-Pro** ساخته شده‌اند (`managed-by=eovpn-pro`) حذف می‌شوند. پروفایل‌های سایر برنامه‌ها دست‌نخورده باقی می‌مانند.»
- هماهنگ‌سازی با داک‌استرینگ `delete_all_connections` در `connection_manager.py:272` و رفتار واقعی `eovpn_nm.c:429`.

**11. ویرایش `eovpn/settings_window.py` (`process_password`، حدود خط ۵۳۱)**
- قطع اتصال از سیگنال تغییر متن؛ اتصال به `activate` و `focus-out` (یا `Gtk.EventControllerFocus`).
- افزودن debounce با `GLib.timeout_add(600, …)` و لغو تایمر قبلی، تا حداکثر یک نوشتن Keyring به‌ازای هر توقف تایپ رخ دهد.

**12. ویرایش `eovpn/utils.py` — `is_private_or_loopback_host`**
- ارتقا از «هشدار» به «نیازمند تأیید صریح»: بازگرداندن یک نتیجه ساخت‌یافته و نمایش `Adw.AlertDialog` قبل از دانلود از میزبان خصوصی/loopback.

**13. ویرایش `dist/flatpak/com.github.mahdi-arts.eovpn-pro.yml`**
- تبدیل همه منابع `type: git` از `tag:` به `commit:` با SHA کامل (NetworkManager، libnma، NetworkManager-openvpn، jsoncpp، libcap-ng، tinyxml2، gdbuspp، libnl، protobuf، openvpn3، eudev).
- ارتقای NetworkManager از `1.38.2` به نسخه پشتیبانی‌شده فعلی.
- بازبینی `-Ddbus_policy_dir=/tmp` و `-Ddbus_system_service_dir=/tmp` در ماژول openvpn3 و جایگزینی با مسیر `/app/...`.

---

### 🟡 فاز P2 — بازآرایی معماری

**14. ایجاد `eovpn/controllers/cascade_controller.py`** *(فایل جدید)*
- انتقال کامل ماشین حالت آبشار از `main_window.py`: تمام ~۱۵ attribute با پیشوند `_cascade_*` (`_cascade_active`, `_cascade_queue`, `_cascade_index`, `_cascade_gen`, `_cascade_failures`, `_cascade_current`, …) و متدهای `_start_cascade`، `_cascade_on_connection_event`، `_finish_cascade`، `_hide_cascade_banner`، `cancel_cascade`، `_set_fastest_button_cancel`، `_set_cascade_controls_locked`.
- کلاس `CascadeController` باید یک اینترفیس view (protocol) بگیرد، نه خود `MainWindow` — تا قابل تست واحد شود.
- افزودن `tests/test_cascade_controller.py`.

**15. ایجاد `eovpn/controllers/network_monitor.py`** *(فایل جدید)*
- انتقال `start_network_monitor`، `stop_network_monitor`، `update_network_speed`.
- بازآرایی: **یک** عبور روی `/proc/net/dev` به‌جای دو عبور؛ انتقال `format_speed`/`format_size` به سطح ماژول (نه closure در هر تیک).
- افزودن تست واحد با ورودی ساختگی `/proc/net/dev`.

**16. ویرایش `eovpn/main_window.py`**
- پس از آیتم‌های ۱۴ و ۱۵، هدف: **زیر ۸۰۰ خط**.
- جایگزینی `class MainWindow(Base, Gtk.Builder)` با composition: `self.builder = Gtk.Builder()`.
- تصحیح `if type(result) is list` → `isinstance(result, list)`.
- افزودن گزینه‌های `it` و `pt_BR` به منوی زبان (هم‌راستا با `po/LINGUAS`) — یا حذف آنها از `LINGUAS` اگر پشتیبانی نمی‌شوند.

**17. ویرایش `eovpn/eovpn_base.py` — کاهش وابستگی به Service-Locator**
- تبدیل `Gio.Settings` به singleton سطح ماژول (`_settings_singleton`) به‌جای نمونه‌سازی در هر `Base.__init__`.
- تولید `Settings.all_settings` به‌صورت پویا از ثابت‌های کلاس (حذف تکرار رشته‌ای و رفع نقض DRY).
- تایپ‌دهی `store()/retrieve()` با `TypeVar`/`Generic` به‌جای `Any` (گام میانی تا حذف کامل رجیستری).
- پاک‌سازی `_session_secrets` هنگام disconnect.

**18. ویرایش `eovpn/connection_manager.py`**
- حذف بدنه از `get_name` (نگه‌داشتن فقط `@abstractmethod ... raise NotImplementedError`) و حذف `__NAME__` بلااستفاده.

**19. ایجاد `eovpn/ovpn_parser.py`** *(فایل جدید)* — رفع وابستگی حلقوی و DRY
- انتقال پارس `.ovpn` (`parse_ovpn_endpoints`, `parse_ovpn_protocols`, `normalize_proto`) به این ماژول خالص.
- `auto_connect.py` و `speed_test.py` هر دو از آن ایمپورت کنند → حذف ایمپورت داخل‌تابعی در `speed_test.parse_ovpn_remote` و حذف پارسر دوم.

**20. ویرایش `eovpn/settings_window.py` (`_build_backend_tab`)**
- حذف نمونه‌سازی `NetworkManager(None)` / `OpenVPN3(None)` صرفاً برای نسخه؛ افزودن `@staticmethod backend_version()` سبک به هر بک‌اند و فراخوانی آن.

**21. مهاجرت APIهای منسوخ GTK4** (چند فایل)
- `Gtk.MessageDialog` → `Adw.AlertDialog`
- `Gtk.FileChooserNative` → `Gtk.FileDialog`
- `Gtk.AboutDialog` → `Adw.AboutWindow`
- `widget.hide()/show()` → `set_visible(False/True)`
- `Gtk.StyleContext.add_provider_for_display` → `Gtk.StyleContext.add_provider_for_display` روی نسخه پشتیبانی‌شده یا `Gtk.CssProvider` مستقیم.

**22. بازآرایی لایه C**
- `subprojects/openvpn3/openvpn3.c`: حذف `static GDBusProxy *UniqueSession` سراسری و انتقال آن به یک context struct که از پایتون تخصیص می‌یابد.
- `subprojects/networkmanager/eovpn_nm.c`: جایگزینی چهار `GMainLoop` تودرتو (خطوط ۱۳۷، ۲۶۰، ۳۲۲، ۳۸۴) با فراخوانی‌های آسنکرون libnm (`nm_client_add_connection_async` و …) و callback به پایتون از طریق `GLib.idle_add`.

---

### 🟢 فاز P3 — پاکسازی و بهداشت مخزن

**23. حذف `.flake8`** و حذف همه ارجاعات به flake8 در `CONTRIBUTING.md`، `README.md`، `docs/RELEASE_CHECKLIST.md`، `requirements-dev.txt` → **ruff تنها لینتر پروژه**.

**24. ویرایش `requirements.txt`** — افزودن newline پایانی و حذف بلوک کامنت ناقص/چسبیده dev.

**25. ویرایش `debian/rules`** — حذف `export PYBUILD_NAME` (بی‌اثر با buildsystem مسون) و حذف `override_dh_auto_install` بی‌اثر.

**26. ویرایش `debian/control`** — افزودن `dh-python` به `Build-Depends` **یا** حذف آن از `scripts/build-deb.sh` و `PACKAGING.md` (یکی از دو).

**27. ویرایش `pyproject.toml`** — تصمیم صریح درباره داستان ساخت: اگر انتشار PyPI هدف نیست، `[build-system]` با `mesonpy` و `twine` از `requirements-dev.txt` حذف و در کامنت توضیح داده شود که این پروژه یک اپلیکیشن سیستمی است.

**28. ویرایش `eovpn/ip_lookup/lookup.py`** — تصحیح داک‌استرینگ `ip_api_https()` (ذکر `api.ipify.org` به‌جای ip-api.com).

**29. ویرایش `eovpn/application.py`** — جایگزینی هک `sys.argv.remove("-c"/"--config")` با `argparse` و `parse_known_args`.

**30. بایگانی گزارش‌های منسوخ** — انتقال `docs/ANALYSIS.md`، `docs/REVIEW.md` و `QA_REPORT.md` به `docs/archive/` (یا ادغام در یک `docs/REVIEW.md` واحد) تا تنها یک منبع حقیقت برای وضعیت پروژه باقی بماند.

**31. افزودن `blueprint-compiler`** به `data/meson.build` برای تولید `otp.ui` از `otp.blp` **یا** حذف `otp.blp` از مخزن (یکی از دو، برای رفع خطر واگرایی).

**32. ویرایش `.gitignore`** — تغییر `tests/data/**` به الگویی دقیق‌تر تا fixtureهای آتی به‌اشتباه نادیده گرفته نشوند.

**33. ایجاد `.github/workflows/codeql.yml`** *(اختیاری، اگر در `ci.yml` ادغام نشد)* — تحلیل ایستای `python` و `cpp` روی زمان‌بندی هفتگی.

**34. ایجاد `docs/THREAT_MODEL.md`** *(فایل جدید، اختیاری)* — مستندسازی مدل تهدید (کانفیگ غیرقابل‌اعتماد، مرز D-Bus، مدیریت راز، زنجیره تأمین) و ثبت تصمیم درباره kill-switch/DNS-leak به‌عنوان کار آتی.

---

### 📋 معیار پذیرش نهایی برای Prompt 2

پس از اجرای فازهای P0 و P1، این‌ها باید همگی برقرار باشند:

- [ ] `.github/workflows/ci.yml` و `release.yml` وجود دارند و روی PR سبز می‌شوند
- [ ] badge CI در README واقعی و سبز است
- [ ] `PKGBUILD` وجود دارد و `makepkg -si` روی Arch کار می‌کند
- [ ] هیچ ادعای CI/CD در `README.md`، `PACKAGING.md`، `SECURITY.md`، `CHANGELOG.md` و `debian/changelog` بدون پشتوانه واقعی نمانده است
- [ ] `python3 -m unittest discover -s tests` همچنان ۱۰۰٪ پاس (و ترجیحاً > ۶۰ تست با تست‌های جدید)
- [ ] `python3 scripts/check_project_meta.py` exit 0
- [ ] `ruff check .` و `mypy` تمیز
- [ ] `pip-audit` بدون CVE
- [ ] تاریخ‌های changelog دیگر در آینده نیستند
- [ ] هیچ مسیر `xdg-open` بدون اعتبارسنجی و هیچ فایل موقت حاوی کلید در `/tmp` سراسری باقی نمانده است

پس از فاز P2، امتیاز هدف: **معماری ۸.۵ · امنیت ۸.۵ · مستندات ۹ · توسعه‌پذیری ۸ · بسته‌بندی ۹ → کلی ≈ ۸.۶**

---

*بازبینی انجام‌شده روی کامیت `e76a9e4` — شاخه `arena/01a028db-eovpn-pro`*
