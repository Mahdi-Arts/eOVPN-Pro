"""
eOVPN-Pro IP Lookup Unit Tests
تست‌های واحد ماژول استعلام IP و موقعیت مکانی در eOVPN-Pro
"""

import unittest
from unittest.mock import MagicMock, patch

from eovpn.ip_lookup.lookup import Lookup


class TestLookup(unittest.TestCase):
    """
    Unit tests for the Lookup class with mocked network responses.
    تست‌های واحد برای اعتبارسنجی استعلام آدرس IP با پاسخ‌های شبیه‌سازی‌شده شبکه.
    """

    @patch('urllib.request.urlopen')
    def test_cloudflare_https_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"ip=198.51.100.42\nts=1600000000\nloc=DE\n"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        lookup = Lookup()
        success = lookup.cloudflare_https()
        self.assertTrue(success)
        self.assertEqual(lookup.ip, "198.51.100.42")
        self.assertEqual(lookup.country_code, "de")

    @patch('urllib.request.urlopen')
    def test_ipapi_co_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b'{"ip": "203.0.113.10", "country_code": "FR", "country_name": "France"}'
        )
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        lookup = Lookup()
        success = lookup.ipapi_co()
        self.assertTrue(success)
        self.assertEqual(lookup.ip, "203.0.113.10")
        self.assertEqual(lookup.country_code, "fr")
        self.assertEqual(lookup.country, "France")

    @patch('urllib.request.urlopen')
    def test_update_fallback(self, mock_urlopen):
        # First call fails, second succeeds
        fail_resp = MagicMock()
        fail_resp.read.side_effect = Exception("Connection Timeout")

        success_resp = MagicMock()
        success_resp.read.return_value = b'{"ip": "1.2.3.4", "country_code": "SE", "country_name": "Sweden"}'
        success_resp.__enter__.return_value = success_resp

        mock_urlopen.side_effect = [Exception("Network error"), success_resp]

        lookup = Lookup()
        result = lookup.update()
        self.assertTrue(result)
        self.assertEqual(lookup.ip, "1.2.3.4")


if __name__ == '__main__':
    unittest.main()
