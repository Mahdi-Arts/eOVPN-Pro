"""
eOVPN-Pro IP & Geolocation Lookup Module
ماژول استعلام آدرس آی‌پی و موقعیت جغرافیایی کاربر در eOVPN-Pro

This module securely retrieves public IP address and geolocation (country code)
using encrypted HTTPS endpoints with multiple redundant fallbacks.
این ماژول آدرس IP عمومی و کد کشور را با استفاده از اندپوینت‌های امن HTTPS
و مکانیزم‌های جایگزین متعدد استعلام می‌کند.
"""

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# Standard browser User-Agent for reliable API access
# هدر استاندارد کاربری جهت جلوگیری از مسدودسازی توسط سرویس‌دهنده‌ها
USER_AGENT = "eOVPN-Pro/1.5 (Linux; GTK4 Client)"
REQUEST_TIMEOUT = 3.5  # seconds / ثانیه


class Lookup:
    """
    Public IP and Geolocation resolver with HTTPS fallbacks.
    کلاس استعلام آدرس IP عمومی و موقعیت مکانی با استفاده از پروتکل امن HTTPS.
    """

    def __init__(self):
        self.ip: str | None = None
        self.country: str | None = None
        self.country_code: str | None = None

        # Redundant HTTPS fallback providers
        # ارائه‌دهندگان جایگزین مبتنی بر پروتکل امن HTTPS
        self.providers = [
            self.cloudflare_https,
            self.ipapi_co,
            self.ip_api_https,
        ]

    def update(self) -> bool:
        """
        Sequentially tries available HTTPS providers until one succeeds.
        تلاش متوالی برای دریافت اطلاعات از ارائه‌دهندگان تا زمان دریافت موفقیت‌آمیز.
        """
        for provider in self.providers:
            try:
                logger.debug("Attempting IP lookup via: %s", provider.__name__)
                if provider():
                    logger.info(
                        "IP lookup succeeded via %s: %s (%s)", provider.__name__, self.ip, self.country_code
                    )
                    return True
            except Exception as exc:
                logger.warning("Provider %s failed: %s", provider.__name__, exc)
                continue

        logger.error("All IP lookup providers failed. Network may be unreachable.")
        return False

    def cloudflare_https(self) -> bool:
        """
        Fetches IP and country from Cloudflare trace endpoint over HTTPS.
        دریافت اطلاعات IP و کشور از سرویس کلودفلر بر بستر HTTPS.
        """
        req = urllib.request.Request(
            "https://www.cloudflare.com/cdn-cgi/trace",
            headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = response.read().decode("utf-8", errors="ignore")
            lines = data.strip().split("\n")
            found_ip = None
            found_loc = None
            for line in lines:
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() == "ip":
                        found_ip = value.strip()
                    elif key.strip() == "loc":
                        found_loc = value.strip().lower()

            if found_ip:
                self.ip = found_ip
                self.country_code = found_loc or "uno"
                self.country = found_loc.upper() if found_loc else "Unknown"
                return True
        return False

    def ipapi_co(self) -> bool:
        """
        Fetches IP and country from ipapi.co over HTTPS.
        دریافت اطلاعات IP و کشور از سرویس ipapi.co بر بستر HTTPS.
        """
        req = urllib.request.Request(
            "https://ipapi.co/json/",
            headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            if "ip" in data:
                self.ip = str(data.get("ip"))
                self.country_code = str(data.get("country_code", "uno")).lower()
                self.country = str(data.get("country_name", "Unknown"))
                return True
        return False

    def ip_api_https(self) -> bool:
        """
        Fetches IP and country from ip-api.com (or json fallback) over HTTPS / JSON.
        دریافت اطلاعات IP و کشور به عنوان گره پشتیبان.
        """
        req = urllib.request.Request(
            "https://api.ipify.org?format=json",
            headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            if "ip" in data:
                self.ip = str(data.get("ip"))
                # If country code not present in simple ipify, retain or fallback to uno
                if not self.country_code:
                    self.country_code = "uno"
                return True
        return False
