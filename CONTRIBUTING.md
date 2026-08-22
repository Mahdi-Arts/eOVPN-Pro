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

# 4. Run linting / بررسی کیفیت کد
python3 -m flake8 eovpn tests run_program_debug.py cffi_compile.py meson_post_install.py

# 5. Build & run locally / ساخت و اجرای محلی
python3 run_program_debug.py   # requires a desktop session / نیازمند نشست گرافیکی
```

---

## 📏 Code Style / سبک کد

- **Python**: PEP 8 with `max-line-length = 110` (see `.flake8`); type hints required on new code.
  PEP 8 با حداکثر طول خط ۱۱۰ (رجوع به `.flake8`)؛ تایپ‌هینت برای کد جدید الزامی است.
- **C**: GNU style via `.clang-format` (4-space indent, 80-column limit).
  سبک GNU با `.clang-format` (تورفتگی ۴ فاصله، حداکثر ۸۰ ستون).
- **Bilingual requirement**: every new docstring, comment, README entry and UI string must
  be written in **English + Persian (فارسی)**. This is a hard project rule.
  **نیازمندی دوزبانه**: هر داک‌استرینگ، کامنت، مطلب README و رشته رابط کاربری جدید باید
  **انگلیسی + فارسی** باشد. این یک قانون الزامی پروژه است.
- **No dead code**: run `python3 -m flake8 .` before pushing; zero warnings expected.
  کد مرده ممنوع؛ پیش از پوش، `flake8` باید بدون هشدار پاس شود.

---

## 🧪 Testing / آزمون

- All tests are offline and mock network I/O / همه تست‌ها آفلاین و با شبیه‌سازی شبکه هستند.
- Add a unit test for every new pure function (e.g. `tests/test_utils.py`).
  برای هر تابع خالص جدید تست واحد بنویسید.
- Never commit `.ovpn`, `.crt`, `.key` or any credential file.
  هرگز فایل‌های `.ovpn`، `.crt`، `.key` یا هر فایل حاوی اعتبارنامه را کامیت نکنید.

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
