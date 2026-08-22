# RPM packaging / بسته‌بندی RPM

## English

The canonical Fedora RPM specification is [`../../eovpn-pro.spec`](../../eovpn-pro.spec).
Keeping a single spec prevents release metadata and dependency drift. Build and
`rpmlint` instructions are maintained in [`../../PACKAGING.md`](../../PACKAGING.md).
The package requires Python 3.10+ and is currently targeted at supported Fedora
releases; RHEL 9's default Python 3.9 is not sufficient.

## فارسی

فایل اصلی و یکتای Spec فدورا در مسیر
[`../../eovpn-pro.spec`](../../eovpn-pro.spec) قرار دارد. نگهداری فقط یک Spec از
ناهماهنگی نسخه و وابستگی‌ها جلوگیری می‌کند. دستور ساخت و `rpmlint` در
[`../../PACKAGING.md`](../../PACKAGING.md) نگهداری می‌شود. بسته به Python 3.10 یا
جدیدتر نیاز دارد و در حال حاضر هدف آن نسخه‌های پشتیبانی‌شده Fedora است؛ Python
پیش‌فرض 3.9 در RHEL 9 کافی نیست.
