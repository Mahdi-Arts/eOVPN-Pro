"""
eOVPN-Pro OpenVPN 3 Backend Package
پکیج بک‌اند OpenVPN 3 در eOVPN-Pro

Provides D-Bus-based integration with the openvpn3-linux system service
for modern VPN tunnel management (DCO, 2FA/OTP, session control).
ارائه‌دهنده یکپارچه‌سازی مبتنی بر D-Bus با سرویس سیستمی openvpn3-linux
برای مدیریت مدرن تونل‌های VPN (DCO، احراز هویت دومرحله‌ای، کنترل نشست).

Note: This backend requires the openvpn3 Python bindings installed.
توجه: این بک‌اند نیازمند نصب بایندینگ‌های پایتون openvpn3 است.
"""

from .dbus import OVPN3Dbus

__all__ = ["OVPN3Dbus"]