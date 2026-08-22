"""Secure configuration importer tests / تست واردکننده امن کانفیگ."""

import io
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import eovpn.config_import as importer
from eovpn.config_import import (
    ArchiveLimitError,
    ConfigurationImportError,
    HTTPSOnlyRedirectHandler,
    InsecureSourceError,
    NoConfigurationsError,
    import_configurations,
)
from eovpn.utils import NotZipException, download_remote_to_destination


class TestConfigurationImporter(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.destination = self.root / "destination"

    def tearDown(self):
        self.temporary.cleanup()

    def _zip(self, entries, name="configs.zip"):
        path = self.root / name
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry_name, content in entries:
                archive.writestr(entry_name, content)
        return path

    def test_local_zip_imports_allowlist_with_private_permissions(self):
        archive = self._zip(
            [
                ("nested/server.ovpn", "proto tcp\nremote example.test 443\n"),
                ("nested/client.key", "PRIVATE"),
                ("nested/ca.crt", "CERT"),
                ("nested/ignored.sh", "echo unsafe"),
            ]
        )
        result = import_configurations(str(archive), self.destination)
        self.assertEqual(result.configs, ("server.ovpn",))
        self.assertEqual(set(result.assets), {"ca.crt", "client.key"})
        self.assertEqual(result.certificates, ("ca.crt",))
        self.assertFalse((self.destination / "ignored.sh").exists())
        self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o700)
        for name in (*result.configs, *result.assets):
            self.assertEqual(stat.S_IMODE((self.destination / name).stat().st_mode), 0o600)

    def test_local_directory_recurses_and_ignores_symlinks(self):
        source = self.root / "source"
        nested = source / "nested"
        nested.mkdir(parents=True)
        (nested / "server.ovpn").write_text("remote test 1194\n", encoding="utf-8")
        (nested / "ca.pem").write_text("CERT", encoding="utf-8")
        (source / "link.ovpn").symlink_to(nested / "server.ovpn")
        result = import_configurations(str(source), self.destination)
        self.assertEqual(result.configs, ("server.ovpn",))
        self.assertEqual(result.assets, ("ca.pem",))

    def test_plain_http_and_insecure_redirect_are_rejected(self):
        with self.assertRaises(InsecureSourceError):
            import_configurations("http://example.test/configs.zip", self.destination)
        with self.assertRaises(InsecureSourceError):
            HTTPSOnlyRedirectHandler().redirect_request(
                MagicMock(), None, 302, "Found", {}, "http://example.test/redirect.zip"
            )

    def test_https_download_is_bounded_and_imported(self):
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w") as archive:
            archive.writestr("server.ovpn", "remote example.test 1194\n")
        response = MagicMock()
        response.headers = {"Content-Length": str(len(memory.getvalue()))}
        response.read.side_effect = [memory.getvalue(), b""]
        response.__enter__.return_value = response
        opener = MagicMock()
        opener.open.return_value = response
        with patch("eovpn.config_import.urllib.request.build_opener", return_value=opener):
            result = import_configurations(
                "https://example.test/configs.zip", self.destination
            )
        self.assertEqual(result.count, 1)

    def test_zip_slip_duplicate_and_symlink_entries_are_rejected(self):
        traversal = self._zip([("../escape.ovpn", "remote test 1\n")], "traversal.zip")
        with self.assertRaises(ConfigurationImportError):
            import_configurations(str(traversal), self.destination)

        duplicate = self._zip(
            [("one/server.ovpn", "remote one 1\n"), ("two/SERVER.ovpn", "remote two 2\n")],
            "duplicate.zip",
        )
        with self.assertRaises(ConfigurationImportError):
            import_configurations(str(duplicate), self.destination)

        symlink_archive = self.root / "symlink.zip"
        with zipfile.ZipFile(symlink_archive, "w") as archive:
            info = zipfile.ZipInfo("link.ovpn")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "target.ovpn")
        with self.assertRaises(ConfigurationImportError):
            import_configurations(str(symlink_archive), self.destination)

    def test_empty_archive_and_invalid_zip_are_rejected(self):
        empty = self._zip([("README.txt", "nothing")], "empty.zip")
        with self.assertRaises(NoConfigurationsError):
            import_configurations(str(empty), self.destination)
        invalid = self.root / "invalid.zip"
        invalid.write_bytes(b"not a zip")
        with self.assertRaises(ConfigurationImportError):
            import_configurations(str(invalid), self.destination)

    def test_security_limits_are_enforced(self):
        archive = self._zip(
            [("server.ovpn", "remote test 1194\n" + "A" * 4096)],
            "large.zip",
        )
        with patch.object(importer, "MAX_ARCHIVE_BYTES", 16):
            with self.assertRaises(ArchiveLimitError):
                import_configurations(str(archive), self.destination)

        many = self._zip(
            [("server.ovpn", "remote test 1\n"), ("ca.crt", "CERT")],
            "many.zip",
        )
        with patch.object(importer, "MAX_ARCHIVE_ENTRIES", 1):
            with self.assertRaises(ArchiveLimitError):
                import_configurations(str(many), self.destination)

        expanded = self._zip(
            [("server.ovpn", "remote test 1\n" + "B" * 1024)],
            "expanded.zip",
        )
        with patch.object(importer, "MAX_EXTRACTED_BYTES", 32):
            with self.assertRaises(ArchiveLimitError):
                import_configurations(str(expanded), self.destination)

    def test_compatibility_wrapper_maps_errors_and_returns_certificates(self):
        archive = self._zip(
            [("server.ovpn", "remote test 1\n"), ("ca.crt", "CERT")],
            "compat.zip",
        )
        self.assertEqual(
            download_remote_to_destination(str(archive), str(self.destination)),
            ["ca.crt"],
        )
        with self.assertRaises(NotZipException):
            download_remote_to_destination(
                str(self.root / "missing.zip"), str(self.root / "other")
            )


if __name__ == "__main__":
    unittest.main()
