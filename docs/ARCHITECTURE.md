# 🏗️ eOVPN-Pro Architecture Overview
# نمای کلی معماری eOVPN-Pro

## High-Level Layers / لایه‌های سطح بالا

```
┌──────────────────────────────────────────────────────────┐
│ UI Layer (GTK4 + Libadwaita)                             │
│  application.py → main_window.py → settings_window.py    │
│  dialogs/otp.py                                          │
├──────────────────────────────────────────────────────────┤
│ Domain Layer / لایه منطق                                 │
│  connection_manager.py  (abstract + 2 backends)          │
│  speed_test.py  utils.py  ip_lookup/lookup.py            │
│  eovpn_base.py  (settings, keyring, notifications)       │
├──────────────────────────────────────────────────────────┤
│ Native Layer / لایه بومی                                 │
│  subprojects/networkmanager/eovpn_nm.c  (libnm via CFFI) │
│  subprojects/openvpn3/openvpn3.c        (D-Bus via CFFI) │
├──────────────────────────────────────────────────────────┤
│ System Services / سرویس‌های سیستم                         │
│  NetworkManager (+ openvpn plugin)  ·  openvpn3-linux    │
│  GNOME Keyring (Secret Service)    ·  GSettings/dconf    │
└──────────────────────────────────────────────────────────┘
```

## Key Design Decisions / تصمیم‌های کلیدی طراحی

### 1. Backend Abstraction / انتزاع بک‌اند
`ConnectionManager` (ABC) defines `connect/disconnect/status/version/start_watch`.
`NetworkManager` and `OpenVPN3` implement it; the UI only talks to the interface.
کلاس انتزاعی `ConnectionManager` متدهای مشترک را تعریف می‌کند و دو بک‌اند آن را
پیاده‌سازی می‌کنند؛ رابط کاربری فقط با اینترفیس صحبت می‌کند.

### 2. Security Boundaries / مرزهای امنیتی
- Secrets: Secret Service ↔ volatile RAM session cache (never dconf/disk).
  رازها: Secret Service ↔ حافظه موقت پروسه (هرگز dconf/دیسک).
- Config imports: strict URL schemes, safe redirects, size caps, Zip-Slip + zip-bomb guards.
  ایمپورت کانفیگ: پروتکل مجاز، ریدایرکت امن، سقف حجم، محافظت Zip-Slip و بمب فشرده.
- Destructive ops: explicit GTK confirmation dialogs / عملیات مخرب: دیالوگ تأیید صریح.

### 3. State Management / مدیریت وضعیت
A small in-memory registry (`Base.store/retrieve`) shares widgets and models between
controllers. It keeps the code simple for a single-window app but should be replaced
by proper dependency injection if multi-window/instance support is added later. Since
the 2026-08 refactor, the long-lived state machines have been extracted into
`cascade_controller.py` and `network_monitor.py`, which receive their dependencies
(host window, timer scheduler) through constructors — the first step towards DI.
یک رجیستری سبک درون‌حافظه‌ای ویجت‌ها و مدل‌ها را بین کنترلرها به اشتراک می‌گذارد.
این طراحی برای برنامه تک‌پنجره ساده و مناسب است؛ در صورت نیاز به چند-نشسته‌شدن،
باید با تزریق وابستگی جایگزین شود. از زمان بازآرایی ۲۰۲۶-۰۸، ماشین‌های حالت بلندمدت
به `cascade_controller.py` و `network_monitor.py` منتقل شده‌اند که وابستگی‌های خود
(پنجره میزبان، زمان‌بند) را از طریق سازنده می‌گیرند — نخستین گام به‌سوی DI.

### 4. Data Flow / جریان داده
- Config list: `Gio.ListStore` → `Gtk.FilterListModel` (search/filter) → `Gtk.ListBox`
- Speed test: worker `ThreadPoolExecutor` → `GLib.idle_add` → UI labels
- IP lookup: worker thread → `GLib.idle_add` → flag/address widgets
- Bandwidth: `GLib.timeout_add_seconds(1)` reading `/proc/net/dev`

## Module Map / نقشه ماژول‌ها

| Module / ماژول | Responsibility / مسئولیت |
|---|---|
| `application.py` | entry point, CLI args, i18n/RTL |
| `eovpn_base.py` | base classes, GSettings, keyring, notifications, favorites |
| `main_window.py` | main UI, search/filter/favorites, event handling, auto-reconnect |
| `settings_window.py` | settings UI, config source, credentials, backend selection |
| `cascade_controller.py` | cascading connect-to-fastest state machine (pure, testable) |
| `network_monitor.py` | `/proc/net/dev` bandwidth poller (single pass per tick) |
| `events.py` | typed connection events (normalizes legacy callback payloads) |
| `timers.py` | injectable timer scheduler (lazy GLib) |
| `ui_compat.py` | version-tolerant dialogs / file pickers (GTK 4.10+ with fallbacks) |
| `_meta.py` | build-time metadata loader for pure modules |
| `connection_manager.py` | abstract + NM + OpenVPN3 managers |
| `speed_test.py` | concurrent TCP latency test |
| `utils.py` | safe ZIP/download, server-filter predicate |
| `ip_lookup/lookup.py` | HTTPS geolocation with fallbacks |
| `backend/*/dbus.py` | D-Bus signal listeners |
| `subprojects/*` | native C bindings (CFFI) |

## Testing Strategy / راهبرد آزمون

Pure modules (`utils`, `speed_test`, `lookup`) are tested offline with mocks.
GTK-dependent code is exercised manually via `run_program_debug.py` and the CI
smoke checks. New pure logic must ship with unit tests.
ماژول‌های خالص با شبیه‌سازی آفلاین تست می‌شوند؛ کد وابسته به GTK به‌صورت دستی و
با چک‌های CI آزمایش می‌شود. منطق خالص جدید باید همراه تست واحد باشد.

---

*یا علی مدد 💚*
