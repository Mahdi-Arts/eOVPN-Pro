# Threat Model / مدل تهدید eOVPN-Pro

## 1. Scope / دامنه

**English:** eOVPN-Pro is an unprivileged desktop controller. It imports user
profiles and asks trusted host services to create a tunnel. The model covers the
Python/GTK process, imported files, Secret Service, CFFI bindings, D-Bus, package
artifacts, and CI supply chain.

**فارسی:** eOVPN-Pro یک کنترلر دسکتاپ بدون امتیاز Root است. برنامه کانفیگ کاربر
را وارد کرده و از سرویس مورد اعتماد میزبان برای ساخت تونل استفاده می‌کند. این
مدل پردازه Python/GTK، فایل‌ها، Secret Service، CFFI، D-Bus، بسته‌ها و زنجیره CI
را پوشش می‌دهد.

## 2. Assets / دارایی‌ها

- VPN username/password, OTP, private keys, certificates, and profile contents.
- Ownership identifiers: NetworkManager UUID and OpenVPN 3 object path.
- Availability and integrity of the previous valid configuration repository.
- User route, DNS, public IP, country, and server endpoint metadata.
- Release source, package checksums, and CI credentials.

- نام کاربری/رمز، OTP، کلید خصوصی، گواهی و محتوای پروفایل VPN.
- شناسه مالکیت شامل UUID و مسیر شیء OpenVPN 3.
- دسترس‌پذیری و صحت مخزن معتبر قبلی.
- مسیر، DNS، IP عمومی، کشور و متادیتای مقصد سرورها.
- سورس انتشار، Checksum بسته‌ها و اعتبارنامه CI.

## 3. Trust boundaries / مرزهای اعتماد

```text
User-selected source -> importer -> private repository
Private repository -> eOVPN process -> Secret Service
Private repository + credentials -> libnm/OpenVPN3 binding -> system D-Bus
System D-Bus -> NetworkManager/OpenVPN3/PolicyKit -> tunnel
Git tag -> GitHub Actions -> .deb/Flatpak/checksums -> user
```

هر پیکان بالا یک مرز اعتبارسنجی است. سرویس VPN، سرور VPN و میزبان خارج از کنترل
مستقیم این برنامه هستند.

## 4. Threats and controls / تهدیدها و کنترل‌ها

| Threat / تهدید | Control / کنترل | Residual risk / ریسک باقی‌مانده |
|---|---|---|
| MITM changes a remote profile | HTTPS-only redirects and bounded download | Compromised trusted provider can still serve a malicious profile |
| ZIP traversal/bomb/symlink | Allowlist, entry/size/ratio bounds, no symlinks, private modes | Local user can intentionally import a large folder up to the configured cap |
| Failed update destroys profiles | Unique staging, validation, same-filesystem swap, rollback | Power loss during filesystem metadata updates remains a host risk |
| Password leaks to dconf/log | Secret Service/RAM only, no secret logs, NM non-save flags | Password necessarily exists in process memory while used |
| eOVPN modifies another VPN | UUID/object-path scope and exact D-Bus subscriptions | A user who can edit their own dconf can already control their NM profiles directly |
| Stale reconnect disconnects new session | Single tracked timer, cancellation, owned status check | Host service races are handled but cannot be eliminated completely |
| Privacy service tracks user | Lookup disabled by default, documented providers, no IP logs | Enabling lookup reveals source IP to the chosen provider |
| Supply-chain drift | Pinned action SHAs, pinned Flatpak commits/hashes, CI validation | GitHub and upstream source availability remain external dependencies |
| Native memory/ABI bug | Compiler warnings, hardening, cppcheck, CFFI ownership/free API | CFFI remains a larger attack surface than pure Python D-Bus |

## 5. Explicit non-goals / موارد خارج از تعهد

- eOVPN-Pro is not a VPN protocol implementation.
- It does not validate the trustworthiness of the VPN provider or server.
- It does not provide a kill switch, firewall policy, DNS leak protection, or
  IPv6 leak protection.
- It cannot secure a compromised kernel, NetworkManager, OpenVPN, desktop
  session, Secret Service, or root account.

- برنامه پیاده‌سازی پروتکل VPN نیست.
- قابل‌اعتمادبودن سرویس‌دهنده یا سرور VPN را تضمین نمی‌کند.
- Kill Switch، Firewall، جلوگیری از نشت DNS یا IPv6 ارائه نمی‌کند.
- میزبان، Kernel، سرویس شبکه، Keyring یا حساب Root آلوده را ایمن نمی‌کند.

## 6. Security regression gates / دروازه جلوگیری از بازگشت امنیتی

A release is blocked unless unit tests, 85% coverage for pure security logic,
flake8, Bandit High, pip-audit, schema/AppStream/Desktop validation, C formatting,
cppcheck, Meson native compilation, Debian build/lint, and Flatpak build pass.

انتشار تا عبور تست‌ها، پوشش ۸۵٪ منطق خالص امنیتی، Flake8، Bandit High، ممیزی
وابستگی، اعتبارسنجی متادیتا، فرمت و تحلیل C، Build بومی، Debian و Flatpak مسدود است.
