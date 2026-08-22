"""
eOVPN-Pro Configuration & Extraction Unit Tests
تست‌های واحد مربوط به استخراج و پردازش کانفیگ‌ها در eOVPN-Pro
"""

import os
import shutil
import tempfile
import unittest
import unittest.mock
import zipfile

from eovpn.utils import (
    MAX_FOLDER_IMPORT_TOTAL_BYTES,
    NotZipException,
    audit_ovpn_content,
    download_remote_to_destination,
    format_data_size,
    format_throughput,
    is_safe_path,
    matches_server_filter,
    ovpn_is_auth_required,
)


class TestOpenVPNUtils(unittest.TestCase):
    """
    Offline unit tests for utility functions, ZIP handling, and Zip-Slip protection.
    تست‌های آفلاین و ایزوله برای بررسی صحت عملکرد توابع کمکی و امنیت فایل‌های فشرده.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="eovpn_test_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_is_safe_path(self):
        """Test Zip-Slip / Path Traversal protection helper."""
        base_dir = os.path.realpath(self.test_dir)
        safe_child = os.path.join(base_dir, "config.ovpn")
        unsafe_traversal = os.path.join(base_dir, "..", "evil.sh")

        self.assertTrue(is_safe_path(base_dir, safe_child))
        self.assertFalse(is_safe_path(base_dir, unsafe_traversal))

    def test_local_folder_import(self):
        """Test importing configurations from a local directory."""
        source_dir = os.path.join(self.test_dir, "source")
        dest_dir = os.path.join(self.test_dir, "dest")
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(dest_dir, exist_ok=True)

        with open(os.path.join(source_dir, "server1.ovpn"), "w") as f:
            f.write("remote 1.2.3.4 1194\n")
        with open(os.path.join(source_dir, "ca.crt"), "w") as f:
            f.write("-----BEGIN CERTIFICATE-----\n-----END CERTIFICATE-----\n")
        with open(os.path.join(source_dir, "ignore.txt"), "w") as f:
            f.write("should be ignored\n")

        certs = download_remote_to_destination(source_dir, dest_dir)
        self.assertIn("ca.crt", certs)
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "server1.ovpn")))
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "ca.crt")))
        self.assertFalse(os.path.exists(os.path.join(dest_dir, "ignore.txt")))

    def test_local_zip_import(self):
        """Test importing configurations from a local ZIP file."""
        zip_path = os.path.join(self.test_dir, "configs.zip")
        dest_dir = os.path.join(self.test_dir, "dest_zip")

        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("nested/vpn_germany.ovpn", "remote de.example.com 1194\nauth-user-pass\n")
            z.writestr("nested/ca.pem", "-----BEGIN CERTIFICATE-----\n-----END CERTIFICATE-----\n")

        certs = download_remote_to_destination(zip_path, dest_dir)
        self.assertIn("ca.pem", certs)
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "vpn_germany.ovpn")))
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "ca.pem")))

    def test_ovpn_is_auth_required(self):
        """Test authentication requirement detection in ovpn files."""
        auth_file = os.path.join(self.test_dir, "auth.ovpn")
        no_auth_file = os.path.join(self.test_dir, "no_auth.ovpn")

        with open(auth_file, "w") as f:
            f.write("client\ndev tun\nauth-user-pass\n")
        with open(no_auth_file, "w") as f:
            f.write("client\ndev tun\n")

        self.assertTrue(ovpn_is_auth_required(auth_file))
        self.assertFalse(ovpn_is_auth_required(no_auth_file))

    def test_invalid_source(self):
        """Test handling invalid source path."""
        invalid_path = os.path.join(self.test_dir, "non_existent_file.xyz")
        dest_dir = os.path.join(self.test_dir, "dest_invalid")
        with self.assertRaises(NotZipException):
            download_remote_to_destination(invalid_path, dest_dir)

    def test_oversized_zip_rejected(self):
        """Test that archives above the size cap are rejected."""
        zip_path = os.path.join(self.test_dir, "huge.zip")
        dest_dir = os.path.join(self.test_dir, "dest_huge")
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("big.ovpn", "remote x 1194\n" + ("A" * 4096))

        with (
            unittest.mock.patch("eovpn.utils.MAX_ZIP_DOWNLOAD_BYTES", 64),
            self.assertRaises(NotZipException),
        ):
            download_remote_to_destination(zip_path, dest_dir)


class TestConfigAudit(unittest.TestCase):
    """
    Tests for the dangerous-directive scanner used on imported configs.
    تست‌های پویش‌گر دایرکتیوهای خطرناک برای کانفیگ‌های واردشده.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="eovpn_audit_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write(self, content: str) -> str:
        path = os.path.join(self.test_dir, "cfg.ovpn")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_flags_script_directives(self):
        path = self._write(
            "client\ndev tun\nup /etc/openvpn/up.sh\ndown /etc/openvpn/down.sh\nremote vpn.example 1194\n"
        )
        self.assertEqual(audit_ovpn_content(path), ["down", "up"])

    def test_flags_script_security_enabler(self):
        path = self._write("script-security 2\nremote vpn.example\n")
        self.assertEqual(audit_ovpn_content(path), ["script-security"])

    def test_plain_auth_user_pass_is_safe(self):
        # The no-argument form is the app's normal Keyring-backed flow.
        # شکل بدون آرگومان، جریان عادی احراز هویت از طریق Keyring است.
        path = self._write("auth-user-pass\nremote vpn.example\n")
        self.assertEqual(audit_ovpn_content(path), [])

    def test_auth_user_pass_with_file_is_flagged(self):
        path = self._write("auth-user-pass /home/user/creds.txt\nremote vpn.example\n")
        self.assertEqual(audit_ovpn_content(path), ["auth-user-pass"])

    def test_safe_config_returns_empty(self):
        path = self._write("client\ndev tun\nproto udp\nremote vpn.example 1194\ncipher AES-256-GCM\n")
        self.assertEqual(audit_ovpn_content(path), [])

    def test_missing_file_returns_empty(self):
        self.assertEqual(audit_ovpn_content(os.path.join(self.test_dir, "nope.ovpn")), [])


class TestFolderImportCap(unittest.TestCase):
    """
    Tests the size cap for local folder imports.
    تست‌های سقف حجم ایمپورت پوشه محلی.
    """

    def test_oversized_folder_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            dest = os.path.join(tmp, "dest")
            os.makedirs(source)
            with open(os.path.join(source, "big.ovpn"), "w") as f:
                f.write("remote x 1194\n" + ("A" * 4096))
            with unittest.mock.patch(
                "eovpn.utils.MAX_FOLDER_IMPORT_TOTAL_BYTES", 64
            ), self.assertRaises(ValueError):
                download_remote_to_destination(source, dest)

    def test_cap_constant_is_sane(self):
        self.assertGreaterEqual(MAX_FOLDER_IMPORT_TOTAL_BYTES, 64 * 1024 * 1024)


class TestFormattingHelpers(unittest.TestCase):
    """
    Tests for the shared human-readable formatting helpers.
    تست‌های کمک‌های قالب‌بندی خوانا و مشترک.
    """

    def test_throughput(self):
        self.assertEqual(format_throughput(512.0), "512.0 B/s")
        self.assertEqual(format_throughput(2048.0), "2.0 KB/s")
        self.assertEqual(format_throughput(5 * 1024 * 1024), "5.0 MB/s")

    def test_data_size(self):
        self.assertEqual(format_data_size(512), "512 B")
        self.assertEqual(format_data_size(2048), "2.0 KB")
        self.assertEqual(format_data_size(3 * 1024 * 1024), "3.0 MB")
        self.assertEqual(format_data_size(2 * 1024 * 1024 * 1024), "2.0 GB")


class TestServerFilter(unittest.TestCase):
    """Unit tests for the pure server-list search/filter predicate."""

    def test_search_matches_substring_case_insensitive(self):
        self.assertTrue(matches_server_filter("iran-tehran.ovpn", search="tehran"))
        self.assertTrue(matches_server_filter("Iran-Tehran.ovpn", search="IRAN"))
        self.assertFalse(matches_server_filter("germany.ovpn", search="france"))

    def test_favorites_mode(self):
        favorites = {"starred.ovpn"}
        self.assertTrue(matches_server_filter("starred.ovpn", mode="favorites", favorites=favorites))
        self.assertFalse(matches_server_filter("plain.ovpn", mode="favorites", favorites=favorites))
        self.assertFalse(matches_server_filter("x.ovpn", mode="favorites", favorites=None))

    def test_online_offline_modes(self):
        latencies = {"fast.ovpn": 42.0, "down.ovpn": None}
        self.assertTrue(matches_server_filter("fast.ovpn", mode="online", latencies=latencies))
        self.assertFalse(matches_server_filter("down.ovpn", mode="online", latencies=latencies))
        self.assertTrue(matches_server_filter("down.ovpn", mode="offline", latencies=latencies))
        self.assertFalse(matches_server_filter("fast.ovpn", mode="offline", latencies=latencies))

    def test_all_mode_always_matches(self):
        self.assertTrue(matches_server_filter("anything.ovpn", mode="all"))

    def test_combined_search_and_mode(self):
        favorites = {"us-ny.ovpn"}
        self.assertTrue(
            matches_server_filter("us-ny.ovpn", search="ny", mode="favorites", favorites=favorites)
        )
        self.assertFalse(
            matches_server_filter("us-ny.ovpn", search="la", mode="favorites", favorites=favorites)
        )


if __name__ == '__main__':
    unittest.main()
