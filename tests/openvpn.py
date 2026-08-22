"""
eOVPN-Pro Configuration & Extraction Unit Tests
تست‌های واحد مربوط به استخراج و پردازش کانفیگ‌ها در eOVPN-Pro
"""

import os
import io
import zipfile
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from eovpn.utils import download_remote_to_destination, ovpn_is_auth_required, NotZipException


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


if __name__ == '__main__':
    unittest.main()
