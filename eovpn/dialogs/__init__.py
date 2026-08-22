"""
eOVPN-Pro Dialog Widgets Package
پکیج ویجت‌های دیالوگ در eOVPN-Pro

Provides reusable dialog windows for user interaction,
including 2FA/OTP verification and confirmation dialogs.
ارائه‌دهنده پنجره‌های دیالوگ قابل استفاده مجدد برای تعامل با کاربر،
از جمله تأیید هویت دومرحله‌ای و دیالوگ‌های تأیید عملیات.
"""

from .otp import OTPInputWindow

__all__ = ["OTPInputWindow"]