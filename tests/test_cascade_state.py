"""
eOVPN-Pro Cascade Controller State Machine Tests
تست‌های ماشین حالت کنترلر اتصال آبشاری eOVPN-Pro

Exercises the extracted ``CascadeController`` offline with a fake host and a
fake timer scheduler — no GTK session required.
ماشین حالت استخراج‌شده ``CascadeController`` را آفلاین با میزبان و زمان‌بند جعلی
تمرین می‌دهد — بدون نیاز به نشست GTK.
"""

import os
import tempfile
import unittest
from collections.abc import Callable
from typing import Any

from eovpn.auto_connect import CascadePhase
from eovpn.cascade_controller import CascadeController
from eovpn.events import ConnectionEvent, ConnectionEventKind


class FakeScheduler:
    """Deterministic in-memory timer scheduler / زمان‌بند قطعی درون‌حافظه‌ای."""

    def __init__(self) -> None:
        self._next_id = 1
        self.timeouts: dict[int, tuple[int, Callable[[], bool]]] = {}

    def add_timeout(self, interval_ms: int, callback: Callable[[], bool]) -> int:
        source_id = self._next_id
        self._next_id += 1
        self.timeouts[source_id] = (interval_ms, callback)
        return source_id

    def add_timeout_seconds(self, interval_seconds: int, callback: Callable[[], bool]) -> int:
        return self.add_timeout(interval_seconds * 1000, callback)

    def remove_timeout(self, source_id: Any) -> None:
        self.timeouts.pop(source_id, None)

    def fire_first(self, interval_ms: int) -> bool | None:
        """Fires the first timeout with the given interval."""
        for source_id, (ms, callback) in list(self.timeouts.items()):
            if ms == interval_ms:
                self.timeouts.pop(source_id)
                return callback()
        return None

    def fire_all(self) -> None:
        for source_id in list(self.timeouts):
            _ms, callback = self.timeouts.pop(source_id)
            callback()


class FakeWidget:
    """Widget stub recording the calls the controller makes."""

    def __init__(self) -> None:
        self.labels: list[str] = []
        self.sensitive: list[bool] = []
        self.css_added: list[str] = []
        self.css_removed: list[str] = []
        self.activations: list[bool] = []
        self.fractions: list[float] = []
        self.reveals: list[bool] = []
        self.spins: list[str] = []

    def set_text(self, text: str) -> None:
        self.labels.append(text)

    def set_label(self, label: str) -> None:
        self.labels.append(label)

    def set_sensitive(self, value: bool) -> None:
        self.sensitive.append(value)

    def add_css_class(self, name: str) -> None:
        self.css_added.append(name)

    def remove_css_class(self, name: str) -> None:
        self.css_removed.append(name)

    def set_active(self, value: bool) -> None:
        self.activations.append(value)

    def set_fraction(self, value: float) -> None:
        self.fractions.append(value)

    def get_fraction(self) -> float:
        return self.fractions[-1] if self.fractions else 0.0

    def set_reveal_child(self, value: bool) -> None:
        self.reveals.append(value)

    def set_tooltip_text(self, value: str) -> None:
        self.labels.append(value)

    def start(self) -> None:
        self.spins.append("start")

    def stop(self) -> None:
        self.spins.append("stop")


class FakeRow:
    """List row stub exposing a filename / بدل ردیف لیست با نام فایل."""

    def __init__(self, filename: str) -> None:
        self.filename = filename


class FakeListBox:
    """ListBox stub consumed by collect_visible_filenames."""

    def __init__(self, filenames: list[str]) -> None:
        self._rows = [FakeRow(name) for name in filenames]

    def get_row_at_index(self, index: int):
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None


class FakeManager:
    """Connection-manager stub / بدل مدیر اتصال."""

    def __init__(self, connected: bool = False) -> None:
        self._connected = connected
        self.connected_paths: list[str] = []
        self.disconnects = 0
        self.watches = 0
        self.cancelled = 0

    def status(self) -> bool:
        return self._connected

    def start_watch(self) -> None:
        self.watches += 1

    def connect(self, path: str) -> None:
        self.connected_paths.append(path)
        self._connected = True

    def disconnect(self) -> None:
        self.disconnects += 1
        self._connected = False

    def cancel_current_operation(self) -> None:
        self.cancelled += 1


class FakeHost:
    """Host window stub satisfying the CascadeHost protocol."""

    def __init__(self, manager: FakeManager | None = None) -> None:
        self.manager = manager if manager is not None else FakeManager()
        self.app = self
        self.window = FakeWidget()
        self.EOVPN_CONFIG_DIR = tempfile.mkdtemp(prefix="eovpn_cfg_")
        self.latencies: dict[str, float | None] = {"a.ovpn": 12.0, "b.ovpn": 30.0}
        self.manual_disconnect = False
        self.sort_by_speed_active = False
        self.list_box = FakeListBox(["a.ovpn", "b.ovpn"])
        self.all_configs = ["a.ovpn", "b.ovpn"]
        self.sort_btn = FakeWidget()
        self.speed_test_btn = FakeWidget()
        self.fastest_btn = FakeWidget()
        self.search_entry = FakeWidget()
        self.filter_dropdown = FakeWidget()
        self.proto_dropdown = FakeWidget()
        self.connect_btn = FakeWidget()
        self.progress_bar = FakeWidget()
        self.cascade_banner = FakeWidget()
        self.cascade_title = FakeWidget()
        self.cascade_meta = FakeWidget()
        self.cascade_bar = FakeWidget()
        self.cascade_spinner = FakeWidget()
        self.cascade_revealer = FakeWidget()
        self.toasts: list[str] = []
        self.speed_tests = 0
        self._selected = "a.ovpn"

    def CM(self):
        return self.manager

    def get_selected_config(self) -> str | None:
        return self._selected

    def get_all_config_filenames(self) -> list[str]:
        return list(self.all_configs)

    def select_server_by_name(self, filename: str) -> bool:
        self._selected = filename
        return True

    def protocols_for(self, filename: str) -> frozenset[str]:
        return frozenset()

    def trigger_speed_test(self) -> None:
        self.speed_tests += 1

    def show_toast(self, message: str, timeout: int = 2) -> None:
        self.toasts.append(message)

    def get_windows(self):
        return [self.window]


class TestCascadeController(unittest.TestCase):
    """State-machine transitions / انتقال‌های ماشین حالت."""

    def setUp(self):
        self.host = FakeHost()
        self.scheduler = FakeScheduler()
        self.clock = [0.0]
        self.controller = CascadeController(self.host, scheduler=self.scheduler, clock=lambda: self.clock[0])
        configs_dir = os.path.join(self.host.EOVPN_CONFIG_DIR, "CONFIGS")
        os.makedirs(configs_dir, exist_ok=True)
        for name in ("a.ovpn", "b.ovpn"):
            with open(os.path.join(configs_dir, name), "w", encoding="utf-8") as handle:
                handle.write("remote vpn.example.com 1194\n")

    def test_start_without_latencies_prepares(self):
        self.host.latencies = {}
        self.controller.start()
        self.assertTrue(self.controller.auto_cascade_after_test)
        self.assertTrue(self.controller.active)
        self.assertEqual(self.controller.phase, CascadePhase.PREPARING)
        self.assertTrue(self.host.sort_btn.activations)
        self.assertIn("Cancel", self.host.fastest_btn.labels)

    def test_start_from_visible_list_connects_first(self):
        self.host.latencies = {"a.ovpn": 12.0, "b.ovpn": 30.0}
        self.controller.start()
        self.assertEqual(self.controller.phase, CascadePhase.CONNECTING)
        self.assertEqual(self.controller.current, "a.ovpn")
        self.assertEqual(len(self.host.manager.connected_paths), 1)
        self.assertTrue(self.host.manager.connected_paths[0].endswith(os.path.join("CONFIGS", "a.ovpn")))
        self.assertEqual(len(self.controller.attempts), 1)
        self.assertGreaterEqual(self.controller.attempts[0].timeout_seconds, 30.0)

    def test_active_candidate_selection_is_reasserted(self):
        self.controller.start()
        self.host._selected = None
        self.controller._update_banner()
        self.assertEqual(self.host._selected, "a.ovpn")

    def test_auto_connect_progress_uses_native_progress_events(self):
        self.controller.start()
        self.assertEqual(self.host.progress_bar.fractions[-1], 0.0)
        self.controller.on_connection_event(ConnectionEvent(ConnectionEventKind.PROGRESS))
        self.assertEqual(self.host.progress_bar.fractions[-1], 0.35)

    def test_queue_scope_is_not_limited_by_visual_filter(self):
        self.host.list_box = FakeListBox(["a.ovpn"])
        self.host.all_configs = ["a.ovpn", "b.ovpn"]
        self.host.latencies = {"a.ovpn": 90.0, "b.ovpn": 10.0}
        self.controller.start()
        self.assertEqual(self.controller.current, "b.ovpn")

    def test_advance_moves_to_next_server(self):
        self.controller.start()
        self.controller.advance("timeout")
        self.assertEqual(self.controller.phase, CascadePhase.SETTLING)
        self.assertEqual(self.controller.failures, [("a.ovpn", "timeout")])
        self.assertEqual(self.controller.index, 1)
        # Firing the settle timer starts the next attempt.
        # شلیک تایمر نشست، تلاش بعدی را آغاز می‌کند.
        self.scheduler.fire_first(550)
        self.assertEqual(self.controller.current, "b.ovpn")

    def test_connected_event_finishes_successfully(self):
        self.controller.start()
        consumed = self.controller.on_connection_event(ConnectionEvent(ConnectionEventKind.CONNECTED))
        self.assertFalse(consumed)
        self.assertFalse(self.controller.active)
        self.assertEqual(self.controller.phase, CascadePhase.SUCCEEDED)
        self.assertEqual(self.controller.attempts[0].result, "success")

    def test_inactive_controller_does_not_consume_normal_backend_events(self):
        self.assertFalse(self.controller.on_connection_event(ConnectionEvent(ConnectionEventKind.CONNECTED)))
        self.assertFalse(
            self.controller.on_connection_event(
                ConnectionEvent(ConnectionEventKind.FAILED, error="normal UI failure")
            )
        )

    def test_failed_event_in_connecting_advances(self):
        self.controller.start()
        consumed = self.controller.on_connection_event(
            ConnectionEvent(ConnectionEventKind.FAILED, error="TLS handshake failed")
        )
        self.assertTrue(consumed)
        self.assertEqual(self.controller.failures[-1], ("a.ovpn", "error"))
        attempt = self.controller.attempts[0]
        self.assertEqual(attempt.error_code, "error")
        self.assertEqual(attempt.error_message, "TLS handshake failed")

    def test_generic_failure_waits_for_handshake_budget(self):
        self.controller.start()
        consumed = self.controller.on_connection_event(
            ConnectionEvent(ConnectionEventKind.FAILED, error="Connection failed")
        )
        self.assertTrue(consumed)
        self.assertTrue(self.controller.active)
        self.assertEqual(self.controller.phase, CascadePhase.CONNECTING)
        self.assertEqual(self.controller.index, 0)

        self.clock[0] = 60.0
        self.controller.advance("timeout", error_code="timeout", error_message="Connection failed")
        self.assertEqual(self.controller.attempts[0].error_code, "timeout")
        self.assertGreaterEqual(self.controller.attempts[0].elapsed_seconds, 60.0)

    def test_auth_failure_reason_detected(self):
        self.controller.start()
        self.controller.on_connection_event(ConnectionEvent(ConnectionEventKind.FAILED, error="AUTH_FAILED"))
        self.assertEqual(self.controller.failures[-1], ("a.ovpn", "auth"))
        self.assertEqual(self.controller.attempts[0].error_code, "auth")
        self.assertEqual(self.controller.attempts[0].error_message, "AUTH_FAILED")

    def test_timeout_callback_advances(self):
        self.controller.start()
        # The handshake never lands: the backend reports disconnected.
        # دست‌دهی هرگز کامل نمی‌شود: بک‌اند قطع گزارش می‌کند.
        self.host.manager._connected = False
        # Fire the armed handshake timeout callback directly.
        # callback تایم‌اوت دست‌دهی مسلح‌شده را مستقیم شلیک کن.
        _interval, callback = self.scheduler.timeouts[self.controller._timeout_id]
        callback()
        self.assertEqual(self.controller.failures[-1], ("a.ovpn", "timeout"))
        self.assertEqual(self.controller.attempts[0].error_code, "timeout")

    def test_fake_clock_records_full_timeout_budget(self):
        self.controller.start()
        self.clock[0] = 60.0
        self.controller.advance("timeout")
        self.assertGreaterEqual(self.controller.attempts[0].elapsed_seconds, 60.0)
        summary = self.controller.attempt_summary()
        self.assertEqual(summary["timeouts"], 1)
        self.assertEqual(summary["attempts"], 1)
        self.assertEqual(summary["candidates"], 2)

    def test_cancel_stops_active_cascade(self):
        self.controller.start()
        self.controller.cancel(user=True)
        self.assertFalse(self.controller.active)
        self.assertEqual(self.controller.phase, CascadePhase.CANCELLED)
        self.assertFalse(self.controller.auto_cascade_after_test)
        self.assertEqual(self.controller.attempts[0].error_code, "cancelled")
        self.assertIsNotNone(self.controller.attempts[0].finished_at)
        self.assertEqual(self.host.manager.cancelled, 1)

    def test_busy_property(self):
        self.assertFalse(self.controller.busy)
        self.host.latencies = {}
        self.controller.start()
        self.assertTrue(self.controller.busy)
        self.controller.cancel()
        self.assertFalse(self.controller.busy)

    def test_controls_locked_during_cascade(self):
        self.controller.start()
        self.assertTrue(self.host.connect_btn.sensitive[-1])  # native button remains the cancel surface
        self.assertTrue(self.host.connect_btn.labels[-1].startswith("Connecting… "))
        self.controller.cancel()
        self.assertTrue(self.host.connect_btn.sensitive[-1])  # unlocked afterwards


if __name__ == "__main__":
    unittest.main()
