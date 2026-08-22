# 🔐 Security Policy
# خط مشی امنیتی eOVPN-Pro

## Supported Versions / نسخه‌های پشتیبانی‌شده

| Version / نسخه | Supported / پشتیبانی |
|---|---|
| 1.5.x | ✅ |

## Reporting a Vulnerability / گزارش آسیب‌پذیری

Please **do not** open a public issue for security problems.
لطفاً برای مشکلات امنیتی **ایسو عمومی باز نکنید**.

Email the maintainer directly / به‌صورت مستقیم به نگه‌دارنده ایمیل بزنید:
- **info@MahdiArts.ir** (primary / اصلی)
- **mehdi.bagheban@gmail.com** (secondary / پشتیبان)

Include: affected version, steps to reproduce, impact estimate, and a suggested fix (optional).
پاسخ معمولاً ظرف ۷۲ ساعت ارسال می‌شود.

## Security Design Notes / نکات طراحی امنیتی

- **Passwords** are stored in the Secret Service (GNOME Keyring) with a dedicated schema and only
  fall back to volatile in-process RAM — never to disk or dconf. The NetworkManager backend marks
  the password as **agent-owned** (`NM_SETTING_SECRET_FLAG_AGENT_OWNED`), so NetworkManager itself
  never writes it to `/etc/NetworkManager/system-connections`.
  **رمزهای عبور** در Secret Service (کی‌رینگ) با اسکیمای اختصاصی ذخیره می‌شوند و تنها در
  حافظه موقت پروسه نگهداری می‌شوند — هرگز روی دیسک یا dconf. بک‌اند NetworkManager رمز را با
  پرچم agent-owned علامت می‌زند تا خود NetworkManager نیز آن را روی دیسک ننویسد.
- **OTP values are never logged** / کدهای یک‌بارمصرف هرگز لاگ نمی‌شوند.
- **ZIP imports** are protected against Zip-Slip, oversized archives and zip bombs; local folder
  imports have a size cap as well.
  **ایمپورت ZIP** در برابر Zip-Slip، آرشیوهای حجیم و بمب فشرده محافظت می‌شود؛ ایمپورت پوشه
  محلی نیز سقف حجم دارد.
- **Downloads** only accept `http`/`https` (including redirects) with a size cap.
  **دانلودها** تنها با پروتکل `http`/`https` (شامل ریدایرکت‌ها) و با سقف حجم انجام می‌شوند.
- **Config audit**: freshly imported `.ovpn` files are scanned for executable directives
  (`up`, `down`, `script-security`, ...) and the user is warned before connecting. Only use
  configs from trusted sources — an OpenVPN config can execute commands with elevated privileges.
  **ممیزی کانفیگ**: کانفیگ‌های تازه واردشده از نظر دایرکتیوهای اجرایی پویش و به کاربر هشدار
  داده می‌شود. فقط از کانفیگ منابع معتبر استفاده کنید — کانفیگ OpenVPN می‌تواند دستورات را
  با اختیارات بالا اجرا کند.
- **Destructive actions** (e.g. "Delete All VPN Connections") require explicit user confirmation.
  **عملیات مخرب** (مانند «حذف همه اتصالات VPN») نیازمند تأیید صریح کاربر هستند.
- **Availability hardening**: every NetworkManager / D-Bus operation has a hard 15-second
  timeout, so a hung service can never freeze the UI.
  **مقاوم‌سازی در دسترس‌پذیری**: همه عملیات NetworkManager / D-Bus تایم‌اوت سخت ۱۵ ثانیه‌ای
  دارند تا سرویس از کار افتاده هرگز رابط کاربری را قفل نکند.
- **GTK thread-safety**: widgets are only touched from the main thread; worker results are
  marshalled back via `GLib.idle_add`.
  **نخ‌امنی GTK**: ویجت‌ها فقط از نخ اصلی دستکاری می‌شوند و نتایج نخ‌های کارگر با
  GLib.idle_add به نخ اصلی بازگردانده می‌شوند.
- **CI security scanning**: `pip-audit` runs on every push; Dependabot keeps GitHub Actions and
  Python dependencies updated weekly.
  **پویش امنیتی CI**: دستور pip-audit روی هر push اجرا می‌شود و Dependabot وابستگی‌ها را
  هفتگی به‌روز می‌کند.

## Known Constraints / محدودیت‌های شناخته‌شده

- The Flatpak manifest ships a patch that disables the NetworkManager plugin ownership check
  (`dist/flatpak/0001-disable-ownership-check-for-plugins.patch`) — required for the sandbox to
  load its own bundled plugin. Keep it minimal and reviewed.
  مانیفست فلت‌پک وصله‌ای دارد که بررسی مالکیت پلاگین NetworkManager را غیرفعال می‌کند —
  لازمه سندباکس برای بارگذاری پلاگین باندل‌شده است. این وصله باید حداقلی و بازبینی‌شده بماند.
- OpenVPN 3 sends configuration contents (which may include inline private keys) and credentials
  over the system D-Bus — this is inherent to the openvpn3 architecture.
  سرویس OpenVPN 3 محتوای کانفیگ (که ممکن است کلید خصوصی inline داشته باشد) و اعتبارنامه را از
  طریق system D-Bus منتقل می‌کند — این ذات معماری openvpn3 است.

## Dependency Responsibility / مسئولیت وابستگی‌ها

Only build dependencies are listed in `debian/control`, `dist/rpm/eovpn-pro.spec` and
`dist/flatpak/...yml`. Runtime secrets never leave the Secret Service boundary.
فقط وابستگی‌های ساخت در فایل‌های بسته‌بندی فهرست می‌شوند. رازهای زمان اجرا هرگز از
مرز Secret Service خارج نمی‌شوند.

*یا علی مدد 💚*
