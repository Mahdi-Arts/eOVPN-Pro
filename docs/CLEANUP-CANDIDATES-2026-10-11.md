# Controlled Cleanup Candidate Manifest — eOVPN-Pro

تاریخ بررسی: ۱۴۰۵/۰۷/۱۹
دامنه: `/home/mahdiarts/Studio/Github/eOVPN-Pro` و lineage مستقیم ثبت‌شده در Git

این سند فقط manifest ممیزی است. هیچ موردی در این مرحله حذف، overwrite، reset یا clean نشده است.

## Candidateها

| مسیر دقیق | وضعیت فعلی | شواهد و reference search | ریسک runtime/build | rollback پیشنهادی | تصمیم |
|---|---|---|---|---|---|
| `/home/mahdiarts/Studio/Github/eOVPN-Pro-v2` | worktree sibling؛ `HEAD=f72d4ad4ea02f5f81c426d5d33040a4d48988834`؛ worktree metadata prunable | در جریان اجرای root استفاده نمی‌شود؛ فقط برای lineage نگه داشته شده است | حذف، مقایسه و recovery تاریخی را از بین می‌برد | پیش از هر حذف، نگهداری ref و ساخت worktree مجدد از همان SHA | `UNKNOWN`؛ نیازمند تأیید مالک |
| `/home/mahdiarts/Studio/Github/eOVPN-Pro-phase0` | worktree sibling؛ همان SHA؛ worktree metadata prunable | در جریان اجرای root استفاده نمی‌شود؛ فقط lineage phase0 است | ممکن است برای provenance و مقایسهٔ rollback لازم باشد | نگهداری SHA و ref متناظر؛ سپس `git worktree add` کنترل‌شده | `UNKNOWN`؛ نیازمند تأیید مالک |
| `eovpn/backend/networkmanager/_libeovpn_nm.so` | generated و ignored؛ hash فعلی `705a83154ff9a7b6aa859da8c3c0d10d1e2c74dffe672a7ddc1c715d50a09098` | runtime source-tree آن را load می‌کند، اما نماد `get_last_error` ندارد؛ build خارج از repository نسخهٔ جدید تولید می‌کند | حذف/overwrite می‌تواند import backend را بشکند | نگهداری hash و rebuild/install کنترل‌شده از Meson | `UNKNOWN`؛ حذف ممنوع تا rebuild مالکانه |
| `eovpn/backend/networkmanager/libeovpn_nm.so` | generated و ignored؛ hash فعلی `7ba7fe768690583c4bf178b1c9ee8f864121aab753dd44b4c6c57cddafb95fb4` | جفت binary runtime source-tree؛ در source workflow تولید نمی‌شود | حذف ممکن است linker dependency CFFI را بشکند | بازسازی هر دو artifact از همان out-of-tree build | `UNKNOWN`؛ حذف ممنوع تا rebuild مالکانه |
| `eovpn/**/__pycache__/**` و `tests/**/__pycache__/**` | generated و ignored | `.gitignore` صریحاً `__pycache__/` را پوشش می‌دهد؛ runtime منبع حقیقت نیست | کم؛ ولی حذف هم‌زمان با اجرای Python race ایجاد می‌کند | اجرای Python دوباره آن‌ها را بازتولید می‌کند | `UNKNOWN`؛ cleanup جداگانه و زمان‌بندی‌شده |
| `dist/` | tracked packaging source؛ شامل AppImage/Arch/Flatpak/RPM metadata و script | `scripts/build-flatpak.sh` به `dist/flatpak/...` ارجاع مستقیم دارد | حذف می‌تواند packaging/CI را بشکند | بازگشت فایل‌های tracked از ref فعلی | `COMPLETED`؛ حفظ شود |
| `cffi_compile.py` | tracked root build helper؛ unstaged modified | `.github/workflows/ci.yml` و Meson/compile workflow به آن ارجاع دارند | حذف، build یا CI را می‌شکند | بازگشت نسخهٔ tracked از ref فعلی | `COMPLETED`؛ حفظ شود |
| `subprojects/networkmanager/cffi_compile.py` | deletion staged و working-tree copy untracked | `subprojects/networkmanager/meson.build` آن را مستقیم در `custom_target` استفاده می‌کند | حذف staged build را می‌شکند | حفظ فایل working-tree تا تصمیم نهایی دربارهٔ index | `COMPLETED` برای source build؛ وضعیت index نیازمند تصمیم Git |
| `docs/PR_BODY_R2.md`, `docs/PR_BODY_R3.md` | deletion staged | reference اجرایی فعلی پیدا نشد؛ اسناد process قدیمی‌اند | خطر runtime پایین؛ provenance مستنداتی از بین می‌رود | restore از staged/index یا commit مرجع | `UNKNOWN`؛ حذف نهایی نیازمند مالک |
| `po/it.po` ارجاع‌های `com.github.jkotra.*` | tracked localization reference قدیمی | `rg` فقط referenceهای قدیمی داخل همین فایل را یافت؛ حذف بدون بررسی ترجمه خطرناک است | ممکن است رشته‌های desktop قدیمی را بی‌صدا حذف کند | restore از ref فعلی | `UNKNOWN`؛ فعلاً حفظ شود |
| `/tmp/eovpn-goal-build.fWpJEb` | out-of-tree temporary build | فقط validation artifact؛ محصول root نیست | low؛ پس از پایان validation قابل جمع‌آوری است، اما log evidence را از بین می‌برد | ساخت دوباره با Meson؛ حفظ تا نهایی‌شدن report | `COMPLETED` برای validation؛ فعلاً حفظ شود |

## موارد خارج از دامنهٔ محصول

- `/home/mahdiarts/Studio/Github/Basij-Tamin/.mimosa` متعلق به پروژهٔ دیگری است و در cleanup eOVPN-Pro شمرده نمی‌شود.
- `.git/FETCH_HEAD` و remote `upstream` provenance Git هستند، نه asset محصول؛ حذف آن‌ها انجام نمی‌شود.

## نتیجه

هیچ candidateای مجوز حذف ندارد. هر حذف آینده باید پس از تأیید مالک، ثبت snapshot/hash، reference audit مجدد و ارائهٔ rollback command انجام شود. حذف recursive یا wildcard مجاز نیست.
