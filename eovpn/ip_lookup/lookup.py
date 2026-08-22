"""
Opt-in public IP and country lookup over bounded HTTPS requests.
استعلام اختیاری IP عمومی و کشور با درخواست‌های محدود HTTPS.

No IP address is written to application logs. Every response and redirect is
bounded and validated before it reaches the UI.
هیچ IP در لاگ برنامه ثبت نمی‌شود و پاسخ‌ها و ریدایرکت‌ها پیش از نمایش، محدود و
اعتبارسنجی می‌شوند.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

USER_AGENT = "eOVPN-Pro/1.5"
REQUEST_TIMEOUT = 3.5
MAX_RESPONSE_BYTES = 64 * 1024


class HTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keeps lookup redirects on HTTPS / نگهداری ریدایرکت استعلام روی HTTPS."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).scheme.lower() != "https":
            raise ValueError("Public IP lookup attempted an insecure redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _validated_ip(value) -> str | None:
    """Returns a normalized IPv4/IPv6 address / بازگرداندن آدرس معتبر و نرمال‌شده."""
    try:
        return str(ipaddress.ip_address(str(value).strip()))
    except ValueError:
        return None


def _validated_country_code(value) -> str | None:
    """Returns a lower-case ISO alpha-2 code / بازگرداندن کد دوحرفی استاندارد کشور."""
    code = str(value or "").strip().lower()
    return code if len(code) == 2 and code.isascii() and code.isalpha() else None


class Lookup:
    """HTTPS provider chain for one isolated lookup / زنجیره HTTPS برای یک استعلام ایزوله."""

    def __init__(self) -> None:
        self.ip: str | None = None
        self.country: str | None = None
        self.country_code: str | None = None
        self.providers = (self.cloudflare_https, self.ipapi_co, self.ipify_https)
        self._opener = urllib.request.build_opener(HTTPSRedirectHandler())

    def _read(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with self._opener.open(request, timeout=REQUEST_TIMEOUT) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit() and int(content_length) > MAX_RESPONSE_BYTES:
                raise ValueError("Public IP provider response is too large.")
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError("Public IP provider response exceeded the size limit.")
            return data

    def update(self) -> bool:
        """Tries providers without logging personal data / تلاش سرویس‌ها بدون ثبت داده شخصی."""
        for provider in self.providers:
            try:
                if provider():
                    logger.debug("Public IP lookup succeeded via %s", provider.__name__)
                    return True
            except Exception as exc:
                logger.debug("Public IP provider %s failed: %s", provider.__name__, exc)
        logger.info("Public IP lookup was unavailable.")
        return False

    def cloudflare_https(self) -> bool:
        """Reads Cloudflare trace over HTTPS / خواندن Trace کلودفلر روی HTTPS."""
        text = self._read("https://www.cloudflare.com/cdn-cgi/trace").decode(
            "utf-8", errors="replace"
        )
        values = dict(
            line.split("=", 1)
            for line in text.splitlines()
            if "=" in line
        )
        ip = _validated_ip(values.get("ip"))
        if not ip:
            return False
        country_code = _validated_country_code(values.get("loc"))
        self.ip = ip
        self.country_code = country_code
        self.country = country_code.upper() if country_code else None
        return True

    def ipapi_co(self) -> bool:
        """Reads IP and country from ipapi.co / دریافت IP و کشور از ipapi.co."""
        payload = json.loads(self._read("https://ipapi.co/json/").decode("utf-8"))
        ip = _validated_ip(payload.get("ip"))
        if not ip:
            return False
        self.ip = ip
        self.country_code = _validated_country_code(payload.get("country_code"))
        country_name = payload.get("country_name")
        self.country = str(country_name)[:128] if country_name else None
        return True

    def ipify_https(self) -> bool:
        """Uses ipify as an IP-only fallback / استفاده از ipify فقط برای IP جایگزین."""
        payload = json.loads(
            self._read("https://api.ipify.org?format=json").decode("utf-8")
        )
        ip = _validated_ip(payload.get("ip"))
        if not ip:
            return False
        self.ip = ip
        self.country_code = None
        self.country = None
        return True
