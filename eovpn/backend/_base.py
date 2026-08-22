"""
eOVPN-Pro Backend Shared Helpers
کمک‌های مشترک بک‌اندهای اتصال eOVPN-Pro

Shared mixins used by both connection backends (NetworkManager and
OpenVPN 3) to avoid duplicating CFFI string-conversion boilerplate.
میکسین‌های مشترک برای هر دو بک‌اند (NetworkManager و OpenVPN 3) تا
کد تکراری تبدیل رشته‌های CFFI تکرار نشود.
"""

from __future__ import annotations

from typing import Any


class CFFIStringMixin:
    """
    Converts CFFI ``char *`` values into Python strings safely.

    ``self.ffi`` must be the cffi API instance of the backend.
    تبدیل امن مقادیر ``char *`` سی‌اف‌آی به رشته پایتون.
    ویژگی ``self.ffi`` باید نمونه cffi مربوط به همان بک‌اند باشد.
    """

    # The cffi API instance is provided by the concrete backend at runtime.
    # نمونه cffi توسط بک‌اند مشخص در زمان اجرا تأمین می‌شود.
    ffi: Any

    def to_cffi_string(self, data, decode: bool = False):
        """
        Returns ``None`` for NULL pointers, otherwise the string (optionally
        UTF-8 decoded) as a bytes object.
        برای اشاره‌گر NULL مقدار None و در غیر این صورت رشته (اختیاری با
        رمزگشایی UTF-8) به‌صورت آبجکت bytes بازگردانده می‌شود.

        :param data: Raw CFFI ``char *`` value.
        :param decode: Whether to UTF-8 decode the returned bytes.
        :return: ``None``, ``bytes`` or ``str``.
        """
        if data == self.ffi.NULL:
            return None
        _str = self.ffi.string(data)
        if decode:
            return _str.decode("utf-8")
        return _str
