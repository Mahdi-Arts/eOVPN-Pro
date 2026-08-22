# 🤝 Contributing to eOVPN-Pro
# مشارکت در توسعه eOVPN-Pro

We welcome contributions! This guide keeps the project clean, bilingual and review-friendly.
از مشارکت شما استقبال می‌کنیم! این راهنما برای تمیز نگه‌داشتن پروژه، دوزبانه بودن و سهولت بازبینی تهیه شده است.

---

## 🚀 Quick Start / شروع سریع

```bash
# 1. Fork & clone / فورک و کلون
git clone https://github.com/Mahdi-Arts/eOVPN-Pro.git
cd eOVPN-Pro

# 2. Install dependencies / نصب وابستگی‌ها
sudo apt install -y meson ninja-build python3-cffi python3-gi \
    libnm-dev libgtk-4-dev libadwaita-1-dev libsecret-1-dev libnotify-dev gettext

# 3. Run the test suite / اجرای تست‌ها
python3 -m unittest discover -s tests -v

# 4. Run linting, formatting and type checks / بررسی کیفیت، قالب و نوع کد
python3 -m ruff check .
python3 -m ruff format --check --diff .
python3 -m mypy eovpn

# 5. Build & run locally / ساخت و اجرای محلی
python3 run_program_debug.py   # requires a desktop session / نیازمند نشست گرافیکی
```

---

## 📏 Code Style / سبک کد

- **Python**: PEP 8 with `line-length = 110`, enforced by **ruff** (configured in `pyproject.toml`
  under `[tool.ruff]`); type hints are required on new code.
  PEP 8 با حداکثر طول خط ۱۱۰ که توسط **ruff** اعمال می‌شود (پیکربندی در `pyproject.toml` بخش
  `[tool.ruff]`)؛ تایپ‌هینت برای کد جدید الزامی است.
- **C**: GNU style via `.clang-format` (4-space indent, 80-column limit).
  سبک GNU با `.clang-format` (تورفتگی ۴ فاصله، حداکثر ۸۰ ستون).
- **Bilingual requirement**: every new docstring, comment, README entry and UI string must
  be written in **English + Persian (فارسی)**. This is a hard project rule.
  **نیازمندی دوزبانه**: هر داک‌استرینگ، کامنت، مطلب README و رشته رابط کاربری جدید باید
  **انگلیسی + فارسی** باشد. این یک قانون الزامی پروژه است.
- **No dead code**: run `python3 -m ruff check .` before pushing; zero warnings expected.
  The same command runs in the `lint` job of CI, so a clean local run means a green pipeline.
  کد مرده ممنوع؛ پیش از پوش، `python3 -m ruff check .` باید بدون هشدار پاس شود. همین دستور در
  جاب `lint` در CI اجرا می‌شود، پس اجرای تمیز محلی یعنی خط لولهٔ سبز.

---

## 🧪 Testing / آزمون

- All tests are offline and mock network I/O / همه تست‌ها آفلاین و با شبیه‌سازی شبکه هستند.
- Add a unit test for every new pure function (e.g. `tests/test_utils.py`).
  برای هر تابع خالص جدید تست واحد بنویسید.
- The extracted controllers (`cascade_controller.py`, `network_monitor.py`) are testable with
  fake hosts/schedulers — no GTK session is required; see `tests/test_cascade_state.py`.
  کنترلرهای استخراج‌شده (`cascade_controller.py` و `network_monitor.py`) با میزبان/زمان‌بند جعلی
  قابل تست هستند و به نشست GTK نیاز ندارند؛ `tests/test_cascade_state.py` را ببینید.
- Never commit `.ovpn`, `.crt`, `.key` or any credential file.
  هرگز فایل‌های `.ovpn`، `.crt`، `.key` یا هر فایل حاوی اعتبارنامه را کامیت نکنید.

---

## 🖥️ Local Debug Run / اجرای محلی برای توسعه

The debug launcher builds the native CFFI bindings with Meson/Ninja and starts the
application straight from the source tree (no system installation). It needs a desktop
session with GTK4 + Libadwaita and NetworkManager with the OpenVPN plugin.

راه‌انداز دیباگ، بایندینگ‌های بومی CFFI را با Meson/Ninja می‌سازد و برنامه را مستقیم از درخت
منبع اجرا می‌کند (بدون نصب سیستمی). نیازمند نشست گرافیکی GTK4 + Libadwaita و NetworkManager
به همراه افزونه OpenVPN است.

```bash
# Requires a running desktop session / نیازمند نشست گرافیکی فعال
python3 run_program_debug.py

# Or with a specific log level / یا با سطح لاگ مشخص
EOVPN_DEBUG=DEBUG python3 run_program_debug.py
```

> `run_program_debug.py` sets `OPENVPN3 = True` automatically when the Python
> `openvpn3` bindings are importable; otherwise it falls back to the
> NetworkManager backend only.
> اسکریپت وقتی بایندینگ پایتون `openvpn3` قابل ایمپورت باشد به‌صورت خودکار `OPENVPN3 = True`
> می‌گذارد؛ در غیر این صورت فقط به بک‌اند NetworkManager بازمی‌گردد.

---

## 🔀 Branching & Pull Requests / برنچ و درخواست ادغام

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Commit with clear bilingual messages: `feat(search): add favorites filter / افزودن فیلتر موردعلاقه‌ها`
3. Push and open a PR against `master`; the CI pipeline (tests + lint + .deb build) must pass.
4. Update `data/com.github.mahdi-arts.eovpn-pro.metainfo.xml` releases and `po/*.po` when changing UI strings.
   هنگام تغییر رشته‌های رابط کاربری، `metainfo` و فایل‌های ترجمه را به‌روزرسانی کنید.

---

## 📦 Packaging Contributions / مشارکت در بسته‌بندی

- Debian packaging lives in `debian/`, RPM spec in `dist/rpm/eovpn-pro.spec`, Flatpak in `dist/flatpak/`.
- Every packaging change must be documented bilingually in `PACKAGING.md` and validated in CI.
  هر تغییر بسته‌بندی باید به‌صورت دوزبانه در `PACKAGING.md` مستند و در CI اعتبارسنجی شود.

---

*یا علی مدد 💚*
