"""
eOVPN-Pro HTTPS Download & SSRF Hardening Tests
تست‌های دانلود امن HTTPS و سخت‌سازی SSRF در eOVPN-Pro

Covers scheme enforcement, redirect downgrade blocking, private/loopback host
blocking and the download size cap — all offline with mocked transport.
پوشش اعمال اجباری HTTPS، مسدودسازی ریدایرکت‌های ناامن، مسدودسازی میزبان‌های
خصوصی/loopback و سقف حجم دانلود — همه آفلاین با شبیه‌سازی ترابری.
"""

import io
import shutil
import tempfile
import unittest
import zipfile
import socket
from unittest.mock import patch

from eovpn.utils import (
    MAX_ZIP_DOWNLOAD_BYTES,
    InsecureSourceError,
    _read_limited,
    _SafeRedirectHandler,
    _resolve_safe_https_host,
    download_remote_to_destination,
    is_hard_blocked_source_host,
    is_private_or_loopback_host,
)


class _FakeResponse:
    """Minimal response object for urlopen mocks / پاسخ کمینه برای mock."""

    def __init__(self, data: bytes, headers: dict[str, str] | None = None):
        self._data = data
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            data, self._data = self._data, b""
            return data
        data, self._data = self._data[:size], self._data[size:]
        return data


class _FakeOpener:
    """Opener stub returning a canned response / بازکننده جعلی با پاسخ از پیش تعیین‌شده."""

    def __init__(self, response: _FakeResponse):
        self._response = response

    def open(self, request, timeout=None):
        return self._response


class _ReqStub:
    """Request stub compatible with HTTPRedirectHandler internals."""

    def __init__(self, url: str):
        self._url = url
        self.headers: dict[str, str] = {}
        self.origin_req_host = "example.com"

    def get_full_url(self) -> str:
        return self._url

    def get_method(self) -> str:
        return "GET"


def _make_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("vpn_server.ovpn", "remote vpn.example.com 1194\n")
    return buffer.getvalue()


class TestHostClassification(unittest.TestCase):
    """Host blocking classification / طبقه‌بندی مسدودسازی میزبان."""

    def test_localhost_variants_blocked(self):
        self.assertTrue(is_hard_blocked_source_host("localhost"))
        self.assertTrue(is_hard_blocked_source_host("localhost.localdomain"))
        self.assertTrue(is_hard_blocked_source_host("router.local"))
        self.assertTrue(is_hard_blocked_source_host("intranet.localhost"))

    def test_literal_private_ips_blocked(self):
        self.assertTrue(is_hard_blocked_source_host("192.168.1.5"))
        self.assertTrue(is_hard_blocked_source_host("10.0.0.1"))
        self.assertTrue(is_hard_blocked_source_host("127.0.0.1"))
        self.assertTrue(is_hard_blocked_source_host("169.254.1.1"))
        self.assertTrue(is_hard_blocked_source_host("[::1]"))

    def test_public_hosts_not_hard_blocked(self):
        self.assertFalse(is_hard_blocked_source_host("vpn.example.com"))
        self.assertFalse(is_hard_blocked_source_host("93.184.216.34"))

    def test_private_classifier_unchanged(self):
        self.assertTrue(is_private_or_loopback_host("10.1.2.3"))
        self.assertFalse(is_private_or_loopback_host("vpn.example.com"))

    @patch("eovpn.utils.socket.getaddrinfo")
    def test_resolved_private_addresses_blocked(self, getaddrinfo):
        getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))]
        with self.assertRaises(InsecureSourceError):
            _resolve_safe_https_host("vpn.example.com", 443)

    @patch("eovpn.utils.socket.getaddrinfo")
    def test_resolved_public_address_is_selected(self, getaddrinfo):
        getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        self.assertEqual(_resolve_safe_https_host("vpn.example.com", 443), "93.184.216.34")


class TestHttpsDownload(unittest.TestCase):
    """Download scheme, SSRF and size enforcement / اعمال پروتکل، SSRF و حجم."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="eovpn_https_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_http_source_rejected(self):
        with self.assertRaises(InsecureSourceError):
            download_remote_to_destination("http://example.com/configs.zip", self.test_dir)

    def test_private_literal_ip_source_blocked(self):
        with self.assertRaises(InsecureSourceError):
            download_remote_to_destination("https://192.168.1.10/configs.zip", self.test_dir)

    def test_localhost_source_blocked(self):
        with self.assertRaises(InsecureSourceError):
            download_remote_to_destination("https://localhost/configs.zip", self.test_dir)

    def test_https_zip_download_succeeds(self):
        response = _FakeResponse(_make_zip_bytes())
        opener = _FakeOpener(response)
        with (patch("eovpn.utils.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]), patch("eovpn.utils.urllib.request.build_opener", return_value=opener)):
            certs = download_remote_to_destination("https://vpn.example.com/configs.zip", self.test_dir)
        self.assertEqual(certs, [])
        self.assertTrue(
            self.test_dir
            and __import__("os").path.exists(__import__("os").path.join(self.test_dir, "vpn_server.ovpn"))
        )

    def test_content_length_cap_rejected(self):
        response = _FakeResponse(b"", headers={"Content-Length": str(MAX_ZIP_DOWNLOAD_BYTES + 1)})
        with self.assertRaises(ValueError):
            _read_limited(response)

    def test_redirect_to_http_blocked(self):
        handler = _SafeRedirectHandler()
        request = _ReqStub("https://vpn.example.com/configs.zip")
        with self.assertRaises(InsecureSourceError):
            handler.redirect_request(request, None, 302, "Found", {}, "http://evil.example.com/x.zip")

    def test_redirect_to_https_allowed(self):
        handler = _SafeRedirectHandler()
        request = _ReqStub("https://vpn.example.com/configs.zip")
        redirected = handler.redirect_request(
            request, None, 302, "Found", {}, "https://cdn.example.com/x.zip"
        )
        self.assertEqual(redirected.get_full_url(), "https://cdn.example.com/x.zip")


if __name__ == "__main__":
    unittest.main()
