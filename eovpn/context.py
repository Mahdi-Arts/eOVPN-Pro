"""
Explicit per-application dependency context.
بستر صریح وابستگی‌ها برای هر نمونه برنامه.

The context replaces module-level service-locator dictionaries. It is created at
GTK activation and passed to windows, signal handlers, and backends, preventing
state leakage across tests or multiple application instances.
این بستر جایگزین دیکشنری سراسری Service Locator است؛ هنگام فعال‌سازی GTK ساخته و
به پنجره‌ها، Handlerها و بک‌اندها تزریق می‌شود تا State میان تست‌ها یا نمونه‌های
برنامه نشت نکند.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ApplicationContext:
    """Small typed container for runtime references / محفظه سبک ارجاع‌های زمان اجرا."""

    values: dict[str, object] = field(default_factory=dict)

    def set(self, key: str, value: object) -> None:
        self.values[key] = value

    def get(self, key: str) -> object | None:
        return self.values.get(key)

    def discard(self, key: str) -> None:
        self.values.pop(key, None)

    def clear(self) -> None:
        self.values.clear()
