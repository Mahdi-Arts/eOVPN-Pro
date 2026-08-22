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
  fall back to volatile in-process RAM — never to disk or dconf.
  **رمزهای عبور** در Secret Service (کی‌رینگ) با اسکیمای اختصاصی ذخیره می‌شوند و تنها در
  حافظه موقت پروسه نگهداری می‌شوند — هرگز روی دیسک یا dconf.
- **OTP values are never logged** / کدهای یک‌بارمصرف هرگز لاگ نمی‌شوند.
- **ZIP imports** are protected against Zip-Slip, oversized archives and zip bombs.
  **ایمپورت ZIP** در برابر Zip-Slip، آرشیوهای حجیم و بمب فشرده محافظت می‌شود.
- **Downloads** only accept `http`/`https` (including redirects) with a size cap.
  **دانلودها** تنها با پروتکل `http`/`https` (شامل ریدایرکت‌ها) و با سقف حجم انجام می‌شوند.
- **Destructive actions** (e.g. "Delete All VPN Connections") require explicit user confirmation.
  **عملیات مخرب** (مانند «حذف همه اتصالات VPN») نیازمند تأیید صریح کاربر هستند.

## Dependency Responsibility / مسئولیت وابستگی‌ها

Only build dependencies are listed in `debian/control`, `eovpn-pro.spec` and
`dist/flatpak/...yml`. Runtime secrets never leave the Secret Service boundary.
فقط وابستگی‌های ساخت در فایل‌های بسته‌بندی فهرست می‌شوند. رازهای زمان اجرا هرگز از
مرز Secret Service خارج نمی‌شوند.

*یا علی مدد 💚*
