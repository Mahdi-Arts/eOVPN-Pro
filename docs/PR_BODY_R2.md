# refactor+ci+security: apply full R2 action plan / اعمال کامل طرح اجرایی بازبینی دوم

## Summary / خلاصه

Implements the complete Senior-review action plan (`docs/REVIEW_SENIOR_2026-08-R2.md`):
CI/CD pipelines, security hardening, architecture refactor, packaging upgrades and
documentation sync — 60 files changed, 25 new tests, all quality gates green.

اجرای کامل طرح اجرایی بازبینی Senior: خطوط CI/CD، سخت‌سازی امنیتی، بازآرایی معماری،
ارتقای بسته‌بندی و همگام‌سازی مستندات — ۶۰ فایل، ۲۵ تست جدید، همه دروازه‌های کیفیت سبز.

## Highlights / نکات کلیدی

### CI/CD (was missing entirely / قبلاً کاملاً غایب بود)
- `.github/workflows/ci.yml` — lint/format/mypy, 81 offline tests on Py 3.10–3.12,
  coverage gate, `pip-audit --strict`, metadata check, Meson build + desktop/AppStream
  validation, smoke builds of `.deb`/`.rpm`/Arch packages.
- `.github/workflows/codeql.yml` — security-extended CodeQL for Python + compiled C bindings.
- `.github/workflows/release.yml` — tag-gated: version parity, all 5 package formats,
  build-provenance attestations, `SHA256SUMS`, GitHub Release.
- Dependabot: grouped weekly updates.

### Security / امنیت
- `cffi>=1.16.0` (resolves CVE-2023-23931 floor), SSRF blocking for localhost/literal
  private IPs, bytearray RAM secrets with active wipe, `"null"` GSettings sentinel removed.
- Native C fixes: latent use-after-free contract in `eovpn_nm.c`, per-call GVariant leak in
  `openvpn3.c`, removed process-wide `UniqueSession` (per-session, thread-safe API).
- `docs/SECURITY-ROADMAP.md` — kill-switch / DNS-leak plan for 1.6.

### Refactor / بازآرایی
- `eovpn/cascade_controller.py` — cascade state machine extracted from MainWindow
  (1797 → 1331 lines), unit-testable with fake host/scheduler.
- `eovpn/network_monitor.py` — single-pass `/proc/net/dev` poller.
- `eovpn/events.py` — typed `ConnectionEvent` replaces `type(result) is list` branching.
- `eovpn/timers.py` — injectable timer scheduler; `eovpn/ui_compat.py` — version-tolerant
  dialogs/pickers; composition over `Gtk.Builder` inheritance; NM ops on worker thread;
  lightweight backend version probes; OTP paste support.

### Packaging & Docs / بسته‌بندی و مستندات
- Real AppRun AppImage wrapper, `scripts/build-rpm.sh`, Debian autopkgtest, PKGBUILD notes,
  deterministic meson-python options, extended metadata checker, README/PACKAGING/SECURITY/
  CHANGELOG/ARCHITECTURE synced with the now-real workflows.

## QA / کنترل کیفیت
```
81/81 unit tests OK · ruff clean · ruff format clean · mypy clean (36 files)
coverage 81% (gate 75%) · check_project_meta OK · workflows YAML validated
```

## Breaking changes / تغییرات سازش‌ناپذیر
None — all legacy public APIs preserved via compatibility aliases.
هیچ — همه APIهای عمومی قدیمی با نام‌های مستعار حفظ شده‌اند.

---
*یا علی مدد 💚*
