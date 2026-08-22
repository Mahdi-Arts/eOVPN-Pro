# Privacy Notice / اطلاعیه حریم خصوصی

## English

eOVPN-Pro has no project-operated analytics, advertising, telemetry, account,
or cloud backend. Settings remain in the desktop GSettings store and imported
profiles remain under the user's private configuration directory.

### Network requests

| Feature | Default | Recipient | Data visible to recipient |
|---|---|---|---|
| Configuration import | User initiated | URL selected by the user | Source IP, TLS metadata, requested URL |
| Public IP lookup | **Off** | Cloudflare, then ipapi.co, then ipify | Source IP, request time, application user-agent |
| TCP latency test | User initiated | Endpoints listed in `.ovpn` files and DNS resolver | Source IP, hostname/port, timing |
| VPN connection | User initiated | Selected VPN provider | Credentials/profile data required by that provider |

Responses are size-bounded. Public IP values and credentials are never included
in application logs. Connection/configuration names may appear in debug logs;
do not publish debug logs without reviewing them.

### Local data

- GSettings: preferences, source location, username, favorites, and owned UUIDs.
- Secret Service: password only after explicit save.
- `~/.config/eovpn/CONFIGS`: imported profiles/assets with `0700/0600` modes.
- NetworkManager/OpenVPN3: one application-owned profile/session while required.

Reset removes imported files and preferences and requests deletion of recorded
NetworkManager profiles and the current username's keyring record. Desktop
backup systems or host service journals remain controlled by the user/OS.

## فارسی

eOVPN-Pro هیچ سامانه تحلیل، تبلیغ، Telemetry، حساب کاربری یا Cloud Backend تحت
مدیریت پروژه ندارد. تنظیمات در GSettings دسکتاپ و کانفیگ‌ها در پوشه خصوصی کاربر
باقی می‌مانند.

### درخواست‌های شبکه

| قابلیت | حالت پیش‌فرض | دریافت‌کننده | داده قابل مشاهده |
|---|---|---|---|
| واردکردن کانفیگ | با اقدام کاربر | URL انتخابی کاربر | IP مبدأ، متادیتای TLS و URL |
| استعلام IP عمومی | **خاموش** | Cloudflare، سپس ipapi.co و ipify | IP مبدأ، زمان و User-Agent برنامه |
| سنجش تأخیر TCP | با اقدام کاربر | مقصدهای فایل `.ovpn` و DNS Resolver | IP مبدأ، Host/Port و زمان‌بندی |
| اتصال VPN | با اقدام کاربر | سرویس‌دهنده انتخابی VPN | اطلاعات لازم احراز هویت و کانفیگ |

حجم پاسخ‌ها محدود است و IP عمومی یا اطلاعات احراز هویت در لاگ برنامه ثبت
نمی‌شود. نام کانفیگ یا اتصال ممکن است در Debug Log دیده شود؛ پیش از انتشار لاگ
آن را بازبینی کنید.

### داده محلی

- GSettings: ترجیحات، منبع، نام کاربری، علاقه‌مندی و UUIDهای متعلق به برنامه.
- Secret Service: رمز فقط پس از ذخیره صریح.
- `~/.config/eovpn/CONFIGS`: کانفیگ و Asset با مجوز `0700/0600`.
- NetworkManager/OpenVPN3: یک پروفایل یا نشست متعلق به برنامه در زمان نیاز.

Reset فایل‌ها و ترجیحات را حذف کرده و حذف پروفایل‌های ثبت‌شده و Secret نام
کاربری فعلی را درخواست می‌کند. Backup دسکتاپ و Journal سرویس میزبان تحت کنترل
کاربر و سیستم‌عامل باقی می‌ماند.
