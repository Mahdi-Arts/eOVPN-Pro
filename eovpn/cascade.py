"""
eOVPN-Pro Cascading Auto-Connect — Pure Presentation Helpers
کمک‌های خالص و بدون UI موتور اتصال آبشاری eOVPN-Pro

Pure functions that turn the raw cascade state (index, total, deadline, RTT)
into user-facing progress values and bilingual labels. Keeping this logic
UI-free makes it unit-testable without a GTK session.
توابع خالصی که وضعیت خام آبشار (اندیس، تعداد کل، مهلت، پینگ) را به مقادیر
پیشرفت و برچسب‌های کاربرپسند تبدیل می‌کنند؛ بدون وابستگی به GTK و کاملاً
تست‌پذیر.
"""

from __future__ import annotations

import gettext

# ---------------------------------------------------------------------------
# Progress math / ریاضیات نوار پیشرفت آبشار
# ---------------------------------------------------------------------------


def cascade_progress_fraction(
    index: int,
    total: int,
    elapsed: float,
    attempt_timeout: float,
) -> float:
    """
    Overall progress of a cascade run on the [0, 1] scale.

    ``fraction = (index + elapsed/attempt_timeout) / total``, clamped to
    ``[0, 1]``. ``total`` defaults to 1 when empty to avoid division by zero.
    پیشرفت کلی یک اجرای آبشاری در بازه [0, 1].
    کسر برابر است با (اندیس + زمان‌گذشته/بودجه تلاش) تقسیم بر تعداد کل،
    و در بازه [0, 1] محدود می‌شود تا هرگز از محدوده خارج نشود.

    :param index: Zero-based index of the current attempt.
    :param total: Total number of attempts (>= 1).
    :param elapsed: Seconds already spent on the current attempt.
    :param attempt_timeout: Timeout budget of the current attempt in seconds.
    :return: Fraction between 0.0 and 1.0.
    """
    total = max(1, int(total))
    attempt_timeout = max(attempt_timeout, 0.001)
    elapsed = max(0.0, elapsed)
    fraction = (index + min(1.0, elapsed / attempt_timeout)) / total
    return min(1.0, max(0.0, fraction))


def cascade_remaining_seconds(deadline: float, now: float) -> int:
    """
    Whole seconds left until the attempt deadline (never negative).
    ثانیه‌های باقی‌مانده تا مهلت تلاش جاری (هرگز منفی نمی‌شود).
    """
    return max(0, int(round(deadline - now)))


def cascade_banner_meta(index: int, total: int, remaining_seconds: int) -> str:
    """
    Compact metadata line for the cascade banner, e.g. ``3/10 · 7s left``.
    خط فرعی فشرده بنر آبشار، مانند ``3/10 · 7s left``.
    """
    total = max(1, int(total))
    return gettext.gettext("{}/{}  ·  {}s left").format(
        min(index + 1, total), total, remaining_seconds
    )


# ---------------------------------------------------------------------------
# Reason labels / برچسب‌های دلیل شکست
# ---------------------------------------------------------------------------

_CASCADE_REASON_LABELS: dict[str, str] = {
    "timeout": gettext.gettext("timed out"),
    "error": gettext.gettext("error"),
    "auth": gettext.gettext("authentication failed"),
    "disconnect": gettext.gettext("disconnected"),
    "missing": gettext.gettext("file missing"),
    "unreachable": gettext.gettext("unreachable"),
}


def cascade_reason_label(reason: str) -> str:
    """
    Human-readable (localized) label for a cascade skip reason.
    برچسب خوانا و محلی‌شده برای دلیل رد شدن یک سرور در آبشار.
    """
    return _CASCADE_REASON_LABELS.get(reason, reason)
