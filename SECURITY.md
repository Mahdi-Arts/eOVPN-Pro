# 🔐 Security Policy
# خط مشی امنیتی eOVPN-Pro

## Supported Versions / نسخه‌های پشتیبانی‌شده

| Version / نسخه | Supported / پشتیبانی |
|---|---|
| 1.5.x | ✅ |
| < 1.5 | ❌ |

## Reporting a Vulnerability / گزارش آسیب‌پذیری

Please **do not** open a public issue for security problems.
لطفاً برای مشکلات امنیتی **ایسو عمومی باز نکنید**.

Email the maintainer directly / به‌صورت مستقیم به نگه‌دارنده ایمیل بزنید:
- **info@MahdiArts.ir** (primary / اصلی)
- **mehdi.bagheban@gmail.com** (secondary / پشتیبان)

Include: affected version, steps to reproduce, impact estimate, and a suggested fix (optional).
موارد زیر را ذکر کنید: نسخهٔ آسیب‌پذیر، گام‌های بازتولید، برآورد اثر و در صورت امکان راه‌حل پیشنهادی.

A first response is normally sent within 72 hours.
پاسخ اولیه معمولاً ظرف ۷۲ ساعت ارسال می‌شود.

---

## Verifying Downloads / راستی‌آزمایی فایل‌های دانلودشده

Every GitHub Release publishes a `SHA256SUMS` manifest covering all package artifacts.
Always verify before installing:
هر انتشار در GitHub، فایل `SHA256SUMS` را برای همهٔ بسته‌ها منتشر می‌کند. پیش از نصب،
حتماً راستی‌آزمایی کنید:

```bash
sha256sum -c SHA256SUMS --ignore-missing
```

> ℹ️ Detached GPG signatures are **not** provided yet; integrity currently relies on the
> checksum manifest plus GitHub's TLS transport and release provenance.
> امضای GPG جداگانه **هنوز** ارائه نمی‌شود؛ یکپارچگی فعلاً بر فایل checksum به همراه
> انتقال TLS و منشأ انتشار GitHub تکیه دارد.

---

## Security Design Notes / نکات طراحی امنیتی

### Credentials / اعتبارنامه‌ها
- **Passwords** are stored in the Secret Service (GNOME Keyring) with a dedicated schema and only
  fall back to volatile in-process RAM — never to disk or dconf. The NetworkManager backend marks
  the password as **agent-owned** (`NM_SETTING_SECRET_FLAG_AGENT_OWNED`), so NetworkManager itself
  never writes it to `/etc/NetworkManager/system-connections`. If that flag cannot be applied, the
  import is aborted rather than falling back to an on-disk secret.
  **رمزهای عبور** در Secret Service (کی‌رینگ) با اسکیمای اختصاصی ذخیره می‌شوند و در غیر این صورت
  تنها در حافظهٔ موقت پروسه نگهداری می‌شوند — هرگز روی دیسک یا dconf. بک‌اند NetworkManager رمز را
  با پرچم agent-owned علامت می‌زند تا خود NetworkManager هم آن را روی دیسک ننویسد؛ اگر اعمال این
  پرچم ممکن نباشد، عملیات ایمپورت متوقف می‌شود و به ذخیرهٔ روی دیسک بازگشت نمی‌کند.
- **OTP values are never logged** and are held only for the duration of a single connection attempt.
  **کدهای یک‌بارمصرف هرگز لاگ نمی‌شوند** و فقط در طول یک تلاش اتصال نگهداری می‌شوند.

### Untrusted input / ورودی غیرقابل‌اعتماد
- **ZIP imports** are protected against Zip-Slip path traversal (validated with `commonpath`),
  oversized archives (64 MiB compressed / 256 MiB extracted), entry-count explosion (20 000 entries),
  symlink entries and duplicate basenames. Files are extracted with `O_NOFOLLOW` and mode `0600`.
  Local folder imports enforce the same total-size cap.
  **ایمپورت ZIP** در برابر پیمایش مسیر (Zip-Slip)، آرشیوهای حجیم (۶۴ مگابایت فشرده / ۲۵۶ مگابایت
  استخراج‌شده)، انفجار تعداد ورودی (۲۰٬۰۰۰ مورد)، ورودی‌های symlink و نام‌های تکراری محافظت می‌شود.
  فایل‌ها با `O_NOFOLLOW` و مجوز `0600` استخراج می‌شوند و ایمپورت پوشهٔ محلی همان سقف حجم را دارد.
- **Remote downloads require HTTPS.** Plain `http://` sources are rejected outright, and the custom
  redirect handler rejects any redirect that leaves HTTPS, so a downgrade cannot be smuggled in
  through a `301`/`302`. Response bodies are read under a hard size cap with a 12-second timeout.
  **دانلودهای راه‌دور فقط با HTTPS** انجام می‌شوند. منابع `http://` مستقیماً رد می‌شوند و
  هندلر ریدایرکت اختصاصی، هر ریدایرکتی را که از HTTPS خارج شود رد می‌کند تا حملهٔ downgrade از
  مسیر `301`/`302` ممکن نباشد. بدنهٔ پاسخ با سقف حجم سخت و تایم‌اوت ۱۲ ثانیه خوانده می‌شود.
- **Config audit**: freshly imported `.ovpn` files are scanned for executable directives
  (`up`, `down`, `route-up`, `script-security`, `plugin`, `learn-address`, `tls-verify`, …) and the
  user is warned before connecting. Only use configs from trusted sources — an OpenVPN config can
  execute commands with elevated privileges.
  **ممیزی کانفیگ**: کانفیگ‌های تازه واردشده از نظر دایرکتیوهای اجرایی پویش می‌شوند و پیش از اتصال
  به کاربر هشدار داده می‌شود. فقط از کانفیگ منابع معتبر استفاده کنید — کانفیگ OpenVPN می‌تواند
  دستورات را با اختیارات بالا اجرا کند.

### Runtime behaviour / رفتار زمان اجرا
- **Destructive actions** (e.g. "Delete All VPN Connections") require explicit user confirmation and
  only ever touch profiles tagged as managed by this application; connections created by other tools
  are never removed.
  **عملیات مخرب** (مانند «حذف همه اتصالات VPN») نیازمند تأیید صریح کاربر است و تنها پروفایل‌هایی را
  حذف می‌کند که توسط همین برنامه ساخته شده‌اند؛ اتصالات ساخته‌شده توسط ابزارهای دیگر دست‌نخورده
  باقی می‌مانند.
- **Availability hardening**: every NetworkManager / D-Bus operation has a hard 15-second
  timeout, so a hung service can never freeze the UI.
  **مقاوم‌سازی در دسترس‌پذیری**: همه عملیات NetworkManager / D-Bus تایم‌اوت سخت ۱۵ ثانیه‌ای
  دارند تا سرویس از کار افتاده هرگز رابط کاربری را قفل نکند.
- **GTK thread-safety**: widgets are only touched from the main thread; worker results are
  marshalled back via `GLib.idle_add`.
  **نخ‌امنی GTK**: ویجت‌ها فقط از نخ اصلی دستکاری می‌شوند و نتایج نخ‌های کارگر با
  `GLib.idle_add` به نخ اصلی بازگردانده می‌شوند.

### Supply chain / زنجیرهٔ تأمین
- **Automated scanning in CI** — `.github/workflows/ci.yml` runs, on every push and pull request:
  `pip-audit --requirement requirements.txt --strict` for known CVEs in Python dependencies.
  `.github/workflows/codeql.yml` runs the security-extended **CodeQL** query packs against the
  Python codebase and the compiled C bindings. A failure in either blocks the merge gate.
  **پویش خودکار در CI** — ورک‌فلوی `.github/workflows/ci.yml` در هر push و pull request دستور
  `pip-audit --requirement requirements.txt --strict` را برای شناسایی CVEهای وابستگی‌های پایتون
  اجرا می‌کند و `.github/workflows/codeql.yml` پکیج‌های security-extended **CodeQL** را روی کدبیس
  پایتون و بایندینگ‌های C اجرا می‌کند؛ شکست هرکدام مانع عبور از دروازهٔ ادغام می‌شود.
- **Dependabot** (`.github/dependabot.yml`) proposes weekly, grouped updates for GitHub Actions
  and Python dependencies.
  **Dependabot** به‌صورت هفتگی به‌روزرسانی‌های گروهی اکشن‌های GitHub و وابستگی‌های پایتون را
  پیشنهاد می‌دهد.
- **Release integrity** — `.github/workflows/release.yml` refuses to publish when the version in
  `meson.build`, `debian/changelog`, the RPM spec, the PKGBUILD, the AppImage script, the AppStream
  metainfo and the README disagree, attaches build-provenance attestations to the `.deb` and
  AppImage artifacts, and ships a `SHA256SUMS` manifest with every release.
  **یکپارچگی انتشار** — ورک‌فلوی `release.yml` در صورت ناهماهنگی نسخه بین `meson.build`،
  `debian/changelog`، اسپک RPM، PKGBUILD، اسکریپت AppImage، متادیتای AppStream و README از انتشار
  خودداری می‌کند، گواهی provenance به `.deb` و AppImage ضمیمه می‌کند و با هر انتشار فایل
  `SHA256SUMS` را منتشر می‌سازد.

---

## Known Constraints / محدودیت‌های شناخته‌شده

These are accepted, documented limitations — not undiscovered bugs.
این موارد محدودیت‌های پذیرفته‌شده و مستندشده‌اند، نه اشکالات کشف‌نشده.

- **No kill-switch or DNS-leak protection.** If the tunnel drops, traffic falls back to the default
  route until the auto-reconnect succeeds. Users with a strict threat model should pair eOVPN-Pro
  with a firewall rule set (e.g. `ufw`/`nftables`) that blocks non-VPN egress.
  **قابلیت kill-switch و محافظت در برابر نشت DNS وجود ندارد.** در صورت قطع تونل، ترافیک تا زمان
  اتصال مجدد از مسیر پیش‌فرض عبور می‌کند. کاربرانی که مدل تهدید سخت‌گیرانه‌ای دارند باید برنامه را
  با مجموعه قواعد فایروال (مانند `ufw`/`nftables`) که خروج غیر VPN را مسدود می‌کند همراه کنند.
- **Private/loopback config sources are blocked when detectable.** Configuration URLs that use
  `localhost` (or `.local`/`.localhost` names) or literal private/loopback/link-local/reserved IP
  addresses are refused outright (SSRF hardening). Unresolved hostnames are still warned about only:
  hostnames are deliberately not resolved before the request, to avoid blocking the UI and leaking
  the source URL to the resolver.
  **منابع کانفیگ خصوصی/loopback در صورت قابل تشخیص بودن مسدود می‌شوند.** آدرس‌هایی که از `localhost`
  (یا نام‌های `.local`/`.localhost`) یا IPهای صریح خصوصی/loopback/link-local/رزرو استفاده می‌کنند
  قاطعانه رد می‌شوند (سخت‌سازی SSRF). نام‌های میزبان حل‌نشده همچنان فقط هشدار می‌گیرند؛ نام میزبان
  عمداً پیش از درخواست resolve نمی‌شود تا رابط کاربری قفل نشود و آدرس منبع به resolver درز نکند.
- **Flatpak plugin ownership patch** — the manifest ships a patch that disables the NetworkManager
  plugin ownership check (`dist/flatpak/0001-disable-ownership-check-for-plugins.patch`), required
  for the sandbox to load its own bundled plugin. Keep it minimal and reviewed.
  **وصلهٔ مالکیت پلاگین در Flatpak** — مانیفست وصله‌ای دارد که بررسی مالکیت پلاگین NetworkManager را
  غیرفعال می‌کند و لازمهٔ بارگذاری پلاگین باندل‌شده در سندباکس است. این وصله باید حداقلی و
  بازبینی‌شده بماند.
- **OpenVPN 3 D-Bus exposure** — OpenVPN 3 sends configuration contents (which may include inline
  private keys) and credentials over the system D-Bus. This is inherent to the openvpn3 architecture
  and is one reason the NetworkManager backend is the default.
  **انتقال داده از طریق D-Bus در OpenVPN 3** — سرویس OpenVPN 3 محتوای کانفیگ (که ممکن است کلید
  خصوصی inline داشته باشد) و اعتبارنامه را از طریق system D-Bus منتقل می‌کند. این ذات معماری
  openvpn3 است و یکی از دلایل پیش‌فرض بودن بک‌اند NetworkManager به شمار می‌رود.
- **Trust in the configuration provider** — eOVPN-Pro validates and audits `.ovpn` files, but a VPN
  provider you connect to can still observe your traffic metadata. Choose providers accordingly.
  **اعتماد به ارائه‌دهندهٔ کانفیگ** — برنامه فایل‌های `.ovpn` را اعتبارسنجی و ممیزی می‌کند، اما
  ارائه‌دهندهٔ VPN که به آن متصل می‌شوید همچنان می‌تواند فراداده‌های ترافیک شما را ببیند.

---

## Dependency Responsibility / مسئولیت وابستگی‌ها

Build and runtime dependencies are declared in `debian/control`, `dist/rpm/eovpn-pro.spec`,
`dist/arch/PKGBUILD` and `dist/flatpak/com.github.mahdi-arts.eovpn-pro.yml`. eOVPN-Pro itself keeps a
deliberately small Python dependency surface (`requirements.txt`) so the audited attack surface stays
minimal. Runtime secrets never leave the Secret Service boundary.

وابستگی‌های ساخت و زمان اجرا در فایل‌های `debian/control`، `dist/rpm/eovpn-pro.spec`،
`dist/arch/PKGBUILD` و مانیفست Flatpak اعلام شده‌اند. سطح وابستگی‌های پایتونی پروژه عمداً کوچک نگه
داشته شده تا سطح حملهٔ قابل ممیزی حداقل بماند. رازهای زمان اجرا هرگز از مرز Secret Service خارج
نمی‌شوند.

---

*یا علی مدد 💚*
