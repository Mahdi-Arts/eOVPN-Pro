"""Offline tests for backend error and cancellation guards."""

import threading
import time
import unittest
from collections import deque
from unittest import mock

from eovpn.connection_manager import NetworkManager, OpenVPN3, OperationCancelled, backend_capabilities


class TestNetworkManagerGuards(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.backend = NetworkManager.__new__(NetworkManager)
        self.backend._operation_cancel = threading.Event()
        self.backend._suppress_callbacks = threading.Event()
        self.backend._operation_state_lock = threading.Lock()
        self.backend._operation_queue = deque()
        self.backend._worker_thread = None
        self.backend.callback = lambda *args: self.events.append(args)

    def test_cancel_sets_gate_and_raise_is_deterministic(self):
        self.backend.cancel_current_operation()
        with self.assertRaises(OperationCancelled):
            self.backend._raise_if_cancelled()

    def test_late_callbacks_are_suppressed_until_next_watch(self):
        self.backend.cancel_current_operation()
        self.backend._guarded_callback(False, "late failure")
        self.assertEqual(self.events, [])

        self.backend._suppress_callbacks.clear()
        self.backend._guarded_callback(True)
        self.assertEqual(self.events, [(True,)])

    def test_native_operations_are_queued_instead_of_dropped(self):
        finished = threading.Event()
        release_first = threading.Event()
        calls = []

        def first_operation():
            calls.append("connect")
            release_first.wait(timeout=1.0)

        def second_operation():
            calls.append("disconnect")
            finished.set()

        self.backend._dispatch_off_ui_thread(first_operation)
        deadline = time.monotonic() + 1.0
        while "connect" not in calls and time.monotonic() < deadline:
            time.sleep(0.01)
        self.backend._dispatch_off_ui_thread(second_operation)
        release_first.set()

        self.assertTrue(finished.wait(timeout=1.0))
        self.assertEqual(calls, ["connect", "disconnect"])


class TestBackendCapabilities(unittest.TestCase):
    def test_capability_report_has_safe_entries_for_each_backend(self):
        capabilities = backend_capabilities()
        self.assertEqual(set(capabilities), {"networkmanager", "openvpn3"})
        for details in capabilities.values():
            self.assertIn("available", details)
            self.assertIn("native_bindings", details)
            self.assertIn("reason", details)

    def test_dco_is_only_advertised_with_openvpn3(self):
        capabilities = backend_capabilities()
        self.assertEqual(capabilities["openvpn3"]["dco"], capabilities["openvpn3"]["available"])

    def test_probe_exceptions_are_reported_as_unknown_not_raised(self):
        with (
            mock.patch.object(NetworkManager, "probe_version", side_effect=RuntimeError("probe failed")),
            mock.patch.object(
                NetworkManager, "probe_cffi_contract", side_effect=RuntimeError("probe failed")
            ),
            mock.patch.object(OpenVPN3, "probe_version", side_effect=RuntimeError("probe failed")),
        ):
            capabilities = backend_capabilities()
        self.assertIsNone(capabilities["networkmanager"]["version"])
        self.assertEqual(capabilities["networkmanager"]["cffi_contract"], "unavailable")
        self.assertIsNone(capabilities["openvpn3"]["version"])


class TestOpenVPN3Ownership(unittest.TestCase):
    def test_disconnect_without_owned_session_does_not_disconnect_everything(self):
        backend = OpenVPN3.__new__(OpenVPN3)
        backend.session_path = None
        backend.callback = mock.Mock()
        backend.ovpn3 = mock.Mock()

        backend.disconnect()

        backend.ovpn3.disconnect_all_sessions.assert_not_called()
        backend.callback.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
