# UI Resources / منابع رابط کاربری

The GTK4 user interfaces are maintained **directly as `.ui` files** (loaded
through `data/eovpn.gresource.xml`). The older `otp.blp` blueprint was removed
to avoid a second, divergent source of truth; if blueprint support is
re-introduced later, `blueprint-compiler` must be wired into `data/meson.build`
so the generated `.ui` can never drift out of sync.

رابط‌های کاربری GTK4 مستقیماً به‌صورت فایل `.ui` نگهداری می‌شوند (بارگذاری از
طریق `data/eovpn.gresource.xml`). بلوپرینت قدیمی `otp.blp` حذف شد تا منبع دومِ
واگرا وجود نداشته باشد؛ اگر در آینده دوباره از blueprint استفاده شود، باید
`blueprint-compiler` به `data/meson.build` متصل شود تا `.ui` تولیدشده هرگز از
هماهنگی خارج نشود.

| File / فایل | Purpose / کاربرد |
|---|---|
| `main.ui` | Main window shell (header bar + layout) / پوسته پنجره اصلی |
| `settings.ui` | Settings window shell / پوسته پنجره تنظیمات |
| `otp.ui` | 2FA/OTP six-digit entry dialog / دیالوگ کد ۶ رقمی OTP |
| `keyboard_shortcuts.ui` | Shortcuts help window / پنجره راهنمای میانبرها |
