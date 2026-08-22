"""Privacy-preserving public IP lookup tests / تست استعلام IP با حفظ حریم خصوصی."""

import unittest
from unittest.mock import patch

from eovpn.ip_lookup.lookup import Lookup, _validated_country_code, _validated_ip


class TestLookup(unittest.TestCase):
    def test_value_validation(self):
        self.assertEqual(_validated_ip("198.51.100.42"), "198.51.100.42")
        self.assertEqual(_validated_ip("2001:db8::1"), "2001:db8::1")
        self.assertIsNone(_validated_ip("not-an-ip"))
        self.assertEqual(_validated_country_code("DE"), "de")
        self.assertIsNone(_validated_country_code("DEU"))
        self.assertIsNone(_validated_country_code("۱۲"))

    def test_cloudflare_success(self):
        lookup = Lookup()
        with patch.object(
            lookup,
            "_read",
            return_value=b"ip=198.51.100.42\nts=1600000000\nloc=DE\n",
        ):
            self.assertTrue(lookup.cloudflare_https())
        self.assertEqual(lookup.ip, "198.51.100.42")
        self.assertEqual(lookup.country_code, "de")

    def test_cloudflare_rejects_invalid_ip(self):
        lookup = Lookup()
        with patch.object(lookup, "_read", return_value=b"ip=invalid\nloc=DE\n"):
            self.assertFalse(lookup.cloudflare_https())

    def test_ipapi_success_and_bounded_country_name(self):
        lookup = Lookup()
        payload = (
            b'{"ip":"203.0.113.10","country_code":"FR","country_name":"France"}'
        )
        with patch.object(lookup, "_read", return_value=payload):
            self.assertTrue(lookup.ipapi_co())
        self.assertEqual(lookup.country_code, "fr")
        self.assertEqual(lookup.country, "France")

    def test_ipify_clears_stale_country(self):
        lookup = Lookup()
        lookup.country_code = "de"
        with patch.object(lookup, "_read", return_value=b'{"ip":"1.2.3.4"}'):
            self.assertTrue(lookup.ipify_https())
        self.assertIsNone(lookup.country_code)

    def test_provider_fallback(self):
        lookup = Lookup()
        lookup.providers = (lambda: False, lambda: True)
        self.assertTrue(lookup.update())

    def test_all_providers_fail(self):
        lookup = Lookup()

        def fail():
            raise OSError("offline")

        lookup.providers = (fail, fail)
        self.assertFalse(lookup.update())


if __name__ == "__main__":
    unittest.main()
