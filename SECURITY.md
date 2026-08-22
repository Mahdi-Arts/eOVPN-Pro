# Security Policy / خط‌مشی امنیتی

## Supported releases / نسخه‌های پشتیبانی‌شده

| Version / نسخه | Status / وضعیت |
|---|---|
| `1.5.x` | Supported after the first signed release / پس از نخستین انتشار امضاشده پشتیبانی می‌شود |
| `< 1.5` | Unsupported / بدون پشتیبانی |

The repository `master` branch is development code and is not a security
release. شاخه `master` کد در حال توسعه است و انتشار امنیتی محسوب نمی‌شود.

## Private reporting / گزارش محرمانه

Do **not** publish credentials, private keys, VPN profiles, or an unpatched
vulnerability in a public issue. Send a report to:

- `info@MahdiArts.ir` — primary / اصلی
- `mehdi.bagheban@gmail.com` — fallback / جایگزین

لطفاً اطلاعات ورود، کلید خصوصی، پروفایل VPN یا آسیب‌پذیری اصلاح‌نشده را در Issue
عمومی منتشر نکنید و گزارش را به ایمیل‌های بالا ارسال کنید.

Include the affected version/commit, backend, distribution, reproduction steps,
impact, and whether the report may be acknowledged publicly. The maintainer aims
to acknowledge reports within 72 hours, provide an initial assessment within
seven days, and coordinate disclosure after a fix is available.

نسخه یا Commit، بک‌اند، توزیع لینوکس، مراحل بازتولید، اثر و اجازه یا عدم اجازه
ذکر نام گزارش‌دهنده را درج کنید. هدف پاسخ اولیه ۷۲ ساعت، ارزیابی اولیه هفت روز و
انتشار هماهنگ پس از آماده‌شدن اصلاح است.

## Security boundaries / مرزهای امنیتی

### Credentials / اطلاعات احراز هویت

- Passwords are persisted only after the explicit **Save Credentials Securely**
  action using Secret Service.
- A process-local RAM copy may exist while the application is running and is
  sent to the selected backend when authentication is required.
- Clearing credentials removes current and legacy Secret Service records for
  that username on a best-effort basis.
- NetworkManager password flags request agent-owned, non-persistent handling.

- رمز فقط پس از اقدام صریح «ذخیره امن» در Secret Service ماندگار می‌شود.
- هنگام اجرا ممکن است نسخه‌ای موقت در RAM وجود داشته باشد و برای احراز هویت به
  بک‌اند انتخابی ارسال شود.
- پاک‌کردن اطلاعات، رکورد فعلی و قدیمی همان نام کاربری را تا حد امکان حذف می‌کند.
- Flags رمز در NetworkManager به‌صورت Agent-owned و غیرماندگار تنظیم می‌شود.

### VPN ownership / مالکیت اتصال VPN

NetworkManager operations are restricted to UUIDs created and recorded by
this application. OpenVPN 3 operations are restricted to one persisted D-Bus
session path. eOVPN must never disconnect or delete an unrelated VPN profile.

عملیات NetworkManager فقط روی UUIDهای ساخته و ثبت‌شده برنامه و عملیات OpenVPN 3
فقط روی مسیر نشست D-Bus متعلق به برنامه انجام می‌شود. eOVPN نباید پروفایل VPN
نامرتبط را قطع یا حذف کند.

### Imported configurations / کانفیگ‌های واردشده

- Remote sources are HTTPS-only, including redirects.
- Compressed size, expanded size, entry count, and compression ratio are bounded.
- Path traversal, duplicate basenames, encrypted entries, and symlinks are rejected.
- The private repository is `0700`; imported files are `0600`.
- A unique staging directory and rollback preserve the previous valid repository.

- منابع راه‌دور و ریدایرکت‌ها فقط HTTPS هستند.
- حجم فشرده/بازشده، تعداد ورودی و نسبت فشرده‌سازی محدود است.
- عبور از مسیر، نام تکراری، ورودی رمزگذاری‌شده و Symlink رد می‌شوند.
- مجوز مخزن `0700` و فایل‌ها `0600` است.
- Staging یکتا و Rollback، نسخه معتبر قبلی را حفظ می‌کند.

A VPN profile is security-sensitive input: it can influence routes, DNS, remote
servers, and cryptographic policy. Import profiles only from a provider you
trust. کانفیگ VPN ورودی حساس است و می‌تواند مسیر، DNS، سرور و سیاست رمزنگاری را
تغییر دهد؛ فقط از سرویس‌دهنده مورد اعتماد وارد کنید.

### Privacy and networking / حریم خصوصی و شبکه

Public IP lookup is disabled by default. If enabled, documented HTTPS providers
receive the user's public IP as an unavoidable part of the request; addresses
are not written to application logs. TCP latency tests occur only after an
explicit user action or **Connect Fastest**. UDP-only endpoints are not probed
with misleading TCP requests.

استعلام IP عمومی پیش‌فرض غیرفعال است. در صورت فعال‌سازی، سرویس HTTPS به‌طور
طبیعی IP عمومی را می‌بیند، اما IP در لاگ برنامه نوشته نمی‌شود. سنجش TCP فقط با
اقدام کاربر یا «اتصال به سریع‌ترین» انجام می‌شود و مقصد UDP با TCP سنجیده نمی‌شود.

## Host trust / اعتماد به میزبان

The application delegates privileged networking to host NetworkManager or the
optional host OpenVPN 3 system service and their PolicyKit/D-Bus policies. It
provides neither a kill switch nor a guarantee against DNS/IPv6 leaks. Flatpak
is a UI sandbox, not a replacement VPN daemon.

عملیات دارای امتیاز به NetworkManager یا سرویس اختیاری OpenVPN 3 و سیاست‌های
PolicyKit/D-Bus میزبان واگذار می‌شود. برنامه Kill Switch یا تضمین جلوگیری از نشت
DNS/IPv6 ارائه نمی‌دهد و Flatpak جایگزین VPN Daemon میزبان نیست.

See [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) and
[`docs/PRIVACY.md`](docs/PRIVACY.md) for the complete model.
برای مدل کامل، اسناد Threat Model و Privacy را مطالعه کنید.
