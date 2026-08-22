# 🗄️ Archived Review Reports / گزارش‌های بازبینی بایگانی‌شده

**English**

The documents in this directory are **historical process artefacts**, not
product documentation. They were written at different points during the 1.5.0
development cycle, each against a different commit, and they contain claims
that were accurate as *intentions* at the time of writing but were never true
of the repository as published.

They are kept for provenance — so the reasoning behind past decisions is not
lost — but they must **not** be treated as a description of the current code.

**فارسی**

اسنادی که در این پوشه قرار دارند **آرتیفکت‌های تاریخی فرایند** هستند و نه مستندات
محصول. هرکدام در مقطعی متفاوت از چرخهٔ توسعهٔ نسخهٔ ۱٫۵٫۰ و روی کامیتی متفاوت
نوشته شده‌اند و حاوی ادعاهایی هستند که در زمان نگارش به‌عنوان *قصد و برنامه* درست
بوده‌اند اما هرگز دربارهٔ مخزنِ منتشرشده صادق نبوده‌اند.

این فایل‌ها برای حفظ سابقه نگهداری می‌شوند تا استدلال پشت تصمیم‌های گذشته از بین
نرود، اما **نباید** به‌عنوان توصیف وضعیت فعلی کد در نظر گرفته شوند.

---

## 📄 Contents / فهرست

| File / فایل | Written against / نوشته‌شده برای | Status / وضعیت |
|---|---|---|
| `REVIEW_2026-08.md` | commit `3b2330c` | Superseded / منسوخ |
| `ANALYSIS_2026-08.md` | commit `710d13d` | Superseded / منسوخ |
| `QA_REPORT_2026-08.md` | delivery report / گزارش تحویل | Superseded / منسوخ |

---

## ⚠️ Known Inaccuracies / نادرستی‌های شناخته‌شده

These are the specific statements that a reader must ignore.
مواردی که خواننده باید نادیده بگیرد:

1. **CI/CD pipeline claims / ادعاهای مربوط به خط لوله CI/CD**
   `QA_REPORT_2026-08.md` states that `.github/workflows/ci-cd.yml` was created,
   and `ANALYSIS_2026-08.md` states that the workflow lives in `dist/ci/`.
   Neither path ever existed in the published tree. A real pipeline was added
   later as **`.github/workflows/ci.yml`** and **`.github/workflows/release.yml`**.

   فایل `QA_REPORT_2026-08.md` مدعی ساخت `.github/workflows/ci-cd.yml` است و
   `ANALYSIS_2026-08.md` می‌گوید workflow در `dist/ci/` قرار دارد. هیچ‌یک از این دو
   مسیر هرگز در درخت منتشرشده وجود نداشت. خط لولهٔ واقعی بعدها با نام‌های
   **`.github/workflows/ci.yml`** و **`.github/workflows/release.yml`** اضافه شد.

2. **Test counts / تعداد تست‌ها**
   The reports quote 12, 18 and 35 tests respectively. The actual suite contains
   **56 tests**; run `python3 -m unittest discover -s tests -v` for the live count.

   این گزارش‌ها به‌ترتیب عدد ۱۲، ۱۸ و ۳۵ تست را ذکر می‌کنند. مجموعهٔ واقعی شامل
   **۵۶ تست** است؛ برای شمارش زنده دستور بالا را اجرا کنید.

3. **Scores / امتیازها**
   The 8.9/10 figure in `QA_REPORT_2026-08.md` assumes the CI pipeline was
   active. The independently verified baseline was **6.5/10**.

   عدد ۸٫۹ از ۱۰ در `QA_REPORT_2026-08.md` بر این فرض استوار است که خط لولهٔ CI
   فعال بوده. مبنای مستقلاً تأییدشده **۶٫۵ از ۱۰** بود.

4. **`flake8` references / ارجاعات به flake8**
   `flake8` and its `.flake8` config were removed from the project; **ruff** is
   now the single linter and formatter, configured in `pyproject.toml`.

   ابزار `flake8` و فایل پیکربندی `.flake8` از پروژه حذف شده‌اند؛ اکنون **ruff**
   تنها لینتر و قالب‌بند پروژه است و پیکربندی آن در `pyproject.toml` قرار دارد.

---

## ✅ Current Sources of Truth / منابع معتبر فعلی

| Topic / موضوع | Document / سند |
|---|---|
| Project overview & install / معرفی و نصب | [`../../README.md`](../../README.md) |
| Architecture / معماری | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) |
| Latest audit / آخرین بازبینی | [`../REVIEW_SENIOR_2026-08.md`](../REVIEW_SENIOR_2026-08.md) |
| Packaging / بسته‌بندی | [`../../PACKAGING.md`](../../PACKAGING.md) |
| Security policy / سیاست امنیتی | [`../../SECURITY.md`](../../SECURITY.md) |
| Release process / فرایند انتشار | [`../RELEASE_CHECKLIST.md`](../RELEASE_CHECKLIST.md) |
| Change history / تاریخچهٔ تغییرات | [`../../CHANGELOG.md`](../../CHANGELOG.md) |
