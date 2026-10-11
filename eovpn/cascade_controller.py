"""
eOVPN-Pro Cascading Auto-Connect Controller
کنترلر اتصال آبشاری به سریع‌ترین سرور در eOVPN-Pro

Owns the full cascade state machine (PREPARING → CONNECTING → SETTLING →
SUCCEEDED / EXHAUSTED / CANCELLED), extracted from ``MainWindow``. The host
window only provides UI widgets, the connection manager and config lookup;
this controller constructs no widgets, holds no GLib references at import
time and is unit-testable with a fake host and a fake scheduler.

مالک کامل ماشین حالت آبشار است که از ``MainWindow`` استخراج شده. پنجره میزبان
فقط ویجت‌ها، مدیر اتصال و دسترسی به کانفیگ‌ها را فراهم می‌کند؛ این کنترلر هیچ
ویجتی نمی‌سازد، در زمان ایمپورت به GLib وابسته نیست و با میزبان و زمان‌بند
جعلی قابل تست واحد است.
"""

from __future__ import annotations

import contextlib
import gettext
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from .auto_connect import (
    DISCONNECT_SETTLE_SECONDS,
    MAX_CASCADE_CANDIDATES,
    PROGRESS_TICK_MS,
    CascadePhase,
    build_cascade_queue,
    collect_visible_filenames,
    compute_attempt_timeout,
    format_proto_badge,
)
from .cascade import (
    cascade_progress_fraction,
)
from .events import ConnectionEvent, ConnectionEventKind
from .speed_state import ConnectionAttempt
from .timers import TimerScheduler, create_default_scheduler

logger = logging.getLogger(__name__)

_ = gettext.gettext


class CascadeHost(Protocol):
    """
    Services the controller expects from its host window.

    خدماتی که کنترلر از پنجره میزبان انتظار دارد.
    """

    app: Any
    window: Any
    EOVPN_CONFIG_DIR: str
    latencies: dict[str, float | None]
    manual_disconnect: bool
    sort_by_speed_active: bool

    list_box: Any
    sort_btn: Any
    speed_test_btn: Any
    fastest_btn: Any
    search_entry: Any
    filter_dropdown: Any
    proto_dropdown: Any
    connect_btn: Any
    progress_bar: Any
    cascade_banner: Any
    cascade_title: Any
    cascade_meta: Any
    cascade_bar: Any
    cascade_spinner: Any
    cascade_revealer: Any

    def CM(self) -> Any: ...
    def get_selected_config(self) -> str | None: ...
    def get_all_config_filenames(self) -> list[str]: ...
    def select_server_by_name(self, filename: str) -> bool: ...
    def protocols_for(self, filename: str) -> frozenset[str]: ...
    def trigger_speed_test(self) -> None: ...
    def show_toast(self, message: str, timeout: int = 2) -> None: ...


class CascadeController:
    """
    Drives the connect-to-fastest cascade with an adaptive handshake timeout.

    هدایت اتصال آبشاری به سریع‌ترین سرور با تایم‌اوت تطبیقی دست‌دهی.
    """

    def __init__(
        self,
        host: CascadeHost,
        scheduler: TimerScheduler | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._win = host
        self._scheduler = scheduler if scheduler is not None else create_default_scheduler()
        self._clock = clock if clock is not None else time.monotonic

        # State / وضعیت
        self.active = False
        self.auto_cascade_after_test = False
        self.phase = CascadePhase.IDLE
        self.gen = 0
        self.queue: list[str] = []
        self.index = 0
        self.deadline = 0.0
        self.current: str | None = None
        self.failures: list[tuple[str, str]] = []
        self.attempts: list[ConnectionAttempt] = []
        self._active_attempt: ConnectionAttempt | None = None
        self.expect_disconnect = False
        self.disconnect_retries = 0
        self._pending_failure_message: str | None = None

        # Scheduler source ids / شناسه‌های زمان‌بند
        self._timeout_id: Any = None
        self._tick_id: Any = None
        self._settle_id: Any = None

    def _now(self) -> float:
        """Read the injected monotonic clock used by timers and tests."""
        return self._clock()

    # ------------------------------------------------------------------
    # Public entry points / نقاط ورود عمومی
    # ------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        """True while a cascade (or its pre-connect speed test) is running."""
        return self.active or self.auto_cascade_after_test

    def attempt_summary(self) -> dict[str, int]:
        """Return stable counters for UI, diagnostics and offline tests."""
        summary = {
            "candidates": len(self.queue),
            "attempts": len(self.attempts),
            "timeouts": 0,
            "handshake_failures": 0,
            "backend_errors": 0,
            "cancelled": 0,
            "success": 0,
        }
        for attempt in self.attempts:
            if attempt.result == "timeout":
                summary["timeouts"] += 1
            elif attempt.result in {"auth", "error", "disconnect"}:
                summary["handshake_failures"] += 1
            elif attempt.result in {"backend_error", "missing"}:
                summary["backend_errors"] += 1
            elif attempt.result == "cancelled":
                summary["cancelled"] += 1
            elif attempt.result == "success":
                summary["success"] += 1
        return summary

    def toggle(self) -> None:
        """Starts the cascade, or cancels it when already busy."""
        if self.busy:
            self.cancel(user=True)
            return
        self.start()

    def start(self) -> None:
        """
        Connects from the first visible (sorted + filtered) server and walks
        down the list with a professional per-attempt handshake timeout.

        اتصال از اولین سرور نمایان (مرتب و فیلترشده) و ادامه روی سرور بعدی در
        صورت شکست دست‌دهی.
        """
        if self.active:
            return

        win = self._win
        candidates = self._candidate_scope()
        if not candidates:
            win.show_toast(_("No VPN configurations are available."))
            return

        if not win.latencies:
            # Measure first so Sort can put the true fastest at the top.
            # ابتدا تست سرعت تا در صورت فعال بودن مرتب‌سازی، سریع‌ترین بالا باشد.
            self.auto_cascade_after_test = True
            self._show_preparing()
            if not win.sort_by_speed_active and hasattr(win, "sort_btn"):
                win.sort_btn.set_active(True)
            else:
                win.trigger_speed_test()
            return

        self.start_from_visible_list()

    def _candidate_scope(self) -> list[str]:
        """Use the full config set, not the current visual filter projection."""
        getter = getattr(self._win, "get_all_config_filenames", None)
        if callable(getter):
            try:
                return [str(name) for name in getter() if name]
            except Exception:
                logger.debug("Could not read complete cascade scope", exc_info=True)
        return collect_visible_filenames(getattr(self._win, "list_box", None))

    def start_from_visible_list(self) -> None:
        """Build the attempt queue from all configs and begin walking it."""
        win = self._win
        candidates = self._candidate_scope()
        queue = build_cascade_queue(candidates, win.latencies, skip_unreachable=True)
        if not queue:
            if self.active:
                self.finish(CascadePhase.EXHAUSTED)
            else:
                win.show_toast(_("No reachable servers in the current list."))
            return

        current = win.get_selected_config()
        try:
            cm = win.CM()
            already = bool(cm and cm.status())
        except Exception:
            already = False

        if already and current == queue[0]:
            if self.active:
                self.current = current
                self.finish(CascadePhase.SUCCEEDED)
            else:
                win.show_toast(_("Already connected to the first server in the list: {}").format(current))
            return

        if len(candidates) > MAX_CASCADE_CANDIDATES:
            win.show_toast(
                _("Auto-connect will try the first {} of {} eligible servers.").format(
                    len(queue), len(candidates)
                )
            )

        self._begin(queue)

    def cancel(self, user: bool = True) -> None:
        """Aborts a running cascade or the pre-connect speed test."""
        if not self.busy:
            return
        logger.info("Cascade cancelled (user=%s)", user)
        try:
            manager = self._win.CM()
            cancel_operation = getattr(manager, "cancel_current_operation", None)
            if callable(cancel_operation):
                cancel_operation()
        except Exception:
            logger.debug("Could not cancel the backend worker cooperatively", exc_info=True)
        self.auto_cascade_after_test = False
        self.gen += 1
        self.finish(CascadePhase.CANCELLED)

    def on_connection_event(self, event: ConnectionEvent) -> bool:
        """
        Consumes D-Bus connection events while a cascade is running.

        Returns True when the regular UI handler must skip the event.

        رویدادهای D-Bus را هنگام اتصال آبشاری مصرف می‌کند؛ مقدار True یعنی
        هندلر عادی UI باید رویداد را نادیده بگیرد.
        """
        if not self.active:
            return False

        if event.kind == ConnectionEventKind.CONNECTED:
            self._disarm_timers()
            self.expect_disconnect = False
            self.finish(CascadePhase.SUCCEEDED, restore_connect_ui=False)
            return False

        if event.kind == ConnectionEventKind.PROGRESS:
            progress = getattr(self._win, "progress_bar", None)
            if progress is not None:
                progress.set_fraction(min(0.95, progress.get_fraction() + 0.35))
            return True

        failed = event.kind in (ConnectionEventKind.FAILED, ConnectionEventKind.DISCONNECTED)
        if not failed:
            return False

        error_text = (event.error or "").lower()
        if self.phase == CascadePhase.SETTLING and self.expect_disconnect:
            self.expect_disconnect = False
            self._win.manual_disconnect = True
            return True

        if self.phase == CascadePhase.CONNECTING:
            reason = "auth" if "auth" in error_text else ("error" if event.error else "disconnect")
            if reason == "error" and not self._is_definitive_backend_failure(error_text):
                # A generic failure signal is not proof that the handshake is
                # terminal. Keep the candidate alive until its 60-second
                # budget expires, then classify it as a timeout.
                self._pending_failure_message = event.error
                self._update_banner()
                return True
            self.advance(reason, error_code=reason, error_message=event.error)
            return True

        return True

    @staticmethod
    def _is_definitive_backend_failure(error_text: str) -> bool:
        markers = (
            "auth_failed",
            "authentication failed",
            "tls handshake failed",
            "certificate",
            "permission denied",
            "invalid configuration",
            "configuration file",
            "unsupported",
            "no such file",
            "backend unavailable",
        )
        return any(marker in error_text for marker in markers)

    # ------------------------------------------------------------------
    # Internal state machine / ماشین حالت داخلی
    # ------------------------------------------------------------------

    def _show_preparing(self) -> None:
        self.active = True
        self.gen += 1
        self.phase = CascadePhase.PREPARING
        self.queue = []
        self.index = 0
        self.current = None
        win = self._win
        if hasattr(win, "cascade_banner"):
            win.cascade_banner.remove_css_class("cascade-success")
            win.cascade_banner.remove_css_class("cascade-fail")
            win.cascade_title.set_text(_("Measuring latency before auto-connect…"))
            win.cascade_meta.set_text("")
            win.cascade_bar.set_fraction(0.0)
            win.cascade_spinner.start()
            win.cascade_revealer.set_reveal_child(False)
        self._set_fastest_button_cancel(True)

    def _begin(self, queue: list[str]) -> None:
        self.gen += 1
        self.active = True
        self.queue = list(queue)
        self.index = 0
        self.failures = []
        self.attempts = []
        self._active_attempt = None
        self.expect_disconnect = False
        self.disconnect_retries = 0
        self.phase = CascadePhase.CONNECTING
        self.current = None
        win = self._win
        win.manual_disconnect = False

        self._set_controls_locked(True)
        self._set_fastest_button_cancel(True)
        if hasattr(win, "connect_btn"):
            win.connect_btn.set_sensitive(True)
            win.connect_btn.set_label(_("Connecting… 30s"))
            win.connect_btn.remove_css_class("suggested-action")
            win.connect_btn.add_css_class("suggested-action")
        if hasattr(win, "progress_bar"):
            win.progress_bar.set_fraction(0.0)
            win.progress_bar.remove_css_class("progress-full-green")
            win.progress_bar.remove_css_class("progress-orange")
            win.progress_bar.add_css_class("progress-yellow")
        if hasattr(win, "cascade_banner"):
            win.cascade_banner.remove_css_class("cascade-success")
            win.cascade_banner.remove_css_class("cascade-fail")
            win.cascade_spinner.start()
            # The selected row and native Connect button identify the active
            # attempt; avoid a second loading card in the connection panel.
            win.cascade_revealer.set_reveal_child(False)

        try:
            cm = win.CM()
            if cm is not None and cm.status():
                self.expect_disconnect = True
                win.manual_disconnect = True
                self.phase = CascadePhase.SETTLING
                self._update_banner(status=_("Disconnecting current session…"))
                cm.start_watch()
                cm.disconnect()
                self._arm_settle(self._try_current_server)
                return
        except Exception as exc:
            logger.error("Cascade pre-disconnect failed: %s", exc)

        self._try_current_server()

    def _try_current_server(self) -> bool:
        if not self.active:
            return False
        if self.index >= len(self.queue):
            self.finish(CascadePhase.EXHAUSTED)
            return False

        win = self._win
        filename = self.queue[self.index]
        self.current = filename
        self.phase = CascadePhase.CONNECTING
        rtt = (win.latencies or {}).get(filename)
        timeout = compute_attempt_timeout(rtt)
        self.deadline = self._now() + timeout
        self._active_attempt = ConnectionAttempt(
            config_id=filename,
            started_at=datetime.now(timezone.utc),
            timeout_seconds=timeout,
        )
        self._pending_failure_message = None
        self.attempts.append(self._active_attempt)
        self._update_connect_button_timer()
        self.expect_disconnect = False
        win.manual_disconnect = False

        win.select_server_by_name(filename)
        # Keep the same visible selection contract as manual Connect: the
        # candidate row is selected before the native backend is invoked.
        if hasattr(win, "get_selected_config") and win.get_selected_config() != filename:
            logger.warning("Cascade selection did not settle for %s", filename)
        self._update_banner()
        self._arm_timeout_and_ticks()

        manager = win.CM()
        if manager is None:
            self.finish(CascadePhase.EXHAUSTED)
            return False
        try:
            manager.start_watch()
            if manager.status():
                self.disconnect_retries += 1
                if self.disconnect_retries > 3:
                    logger.warning("Cascade: still connected after disconnect retries")
                    self.advance("disconnect")
                    return False
                self.expect_disconnect = True
                win.manual_disconnect = True
                self.phase = CascadePhase.SETTLING
                manager.disconnect()
                self._arm_settle(self._try_current_server)
                return False
            self.disconnect_retries = 0
            path = os.path.join(win.EOVPN_CONFIG_DIR, "CONFIGS", filename)
            if not os.path.isfile(path):
                logger.warning("Cascade: missing config %s", path)
                self.advance(
                    "missing",
                    error_code="config_missing",
                    error_message=f"Configuration file is missing: {filename}",
                )
                return False
            manager.connect(path)
        except Exception as exc:
            logger.error("Cascade connect error for %s: %s", filename, exc)
            self.advance("error", error_code="backend_error", error_message=str(exc))
        return False

    def _update_banner(self, status: str | None = None) -> None:
        win = self._win
        if not hasattr(win, "cascade_title"):
            return
        total = max(1, len(self.queue))
        idx = min(self.index + 1, total)
        name = self.current or ""
        if name and hasattr(win, "get_selected_config") and hasattr(win, "select_server_by_name"):
            # Sorting/filter model refreshes can clear ListBox selection after
            # the native connect call. Reassert the active candidate while its
            # attempt is alive so the user always knows what is being tried.
            with contextlib.suppress(Exception):
                if win.get_selected_config() != name:
                    win.select_server_by_name(name)
        rtt = (win.latencies or {}).get(name)
        proto = format_proto_badge(win.protocols_for(name)) if name else ""
        if status:
            win.cascade_title.set_text(status)
        else:
            extras = [part for part in (proto, f"{rtt} ms" if rtt is not None else "") if part]
            suffix = f"  ·  {' · '.join(extras)}" if extras else ""
            win.cascade_title.set_text(_("Trying {}{}").format(name, suffix))
        # Keep the native status compact: progress is conveyed by the bar,
        # while the text only identifies the current attempt.
        win.cascade_meta.set_text(_("Attempt {}/{}").format(idx, total))

        attempt_timeout = compute_attempt_timeout(rtt)
        elapsed = attempt_timeout - max(0.0, self.deadline - self._now())
        overall = cascade_progress_fraction(self.index, total, elapsed, attempt_timeout)
        win.cascade_bar.set_fraction(overall)

    def _update_connect_button_timer(self) -> None:
        """Show the remaining budget only for the automatic cascade button."""
        button = getattr(self._win, "connect_btn", None)
        if button is None or not self.active or self.current is None:
            return
        now = self._now()
        if self.deadline <= now:
            self._on_timeout(self.gen)
            return
        remaining = max(1, int(self.deadline - now))
        button.set_label(_("Connecting… {}s").format(remaining))

    def _arm_timeout_and_ticks(self) -> None:
        self._disarm_timers(keep_settle=False)
        remaining_ms = max(250, int((self.deadline - self._now()) * 1000))
        gen = self.gen
        self._timeout_id = self._scheduler.add_timeout(remaining_ms, lambda: self._on_timeout(gen))
        self._tick_id = self._scheduler.add_timeout(PROGRESS_TICK_MS, lambda: self._on_tick(gen))

    def _disarm_timers(self, keep_settle: bool = False) -> None:
        source_ids = [("_timeout_id", self._timeout_id), ("_tick_id", self._tick_id)]
        if not keep_settle:
            source_ids.append(("_settle_id", self._settle_id))
        for attr, source_id in source_ids:
            if source_id is not None:
                with contextlib.suppress(Exception):
                    self._scheduler.remove_timeout(source_id)
                setattr(self, attr, None)

    def _on_tick(self, gen: int) -> bool:
        if not self.active or gen != self.gen:
            return False
        if self._user_is_busy():
            # Freeze the deadline while an OTP / modal dialog is open.
            # توقف شمارش معکوس وقتی دیالوگ OTP یا مودال باز است.
            self.deadline += PROGRESS_TICK_MS / 1000.0
            return True
        if self.deadline <= self._now():
            self._on_timeout(gen)
            return False
        self._update_banner()
        self._update_connect_button_timer()
        return True

    def _on_timeout(self, gen: int) -> bool:
        self._timeout_id = None
        if not self.active or gen != self.gen:
            return False
        if self._user_is_busy():
            self.deadline = self._now() + 4.0
            self._arm_timeout_and_ticks()
            return False
        logger.info("Cascade handshake timeout on %s", self.current)
        self.advance(
            "timeout",
            error_code="timeout",
            error_message=self._pending_failure_message or "Handshake timeout expired.",
        )
        return False

    def _user_is_busy(self) -> bool:
        """True when a modal dialog (OTP, etc.) is waiting for the user."""
        try:
            for win in self._win.app.get_windows():
                if win is not self._win.window and win.get_mapped() and win.get_modal():
                    return True
        except Exception:
            pass
        return False

    def _arm_settle(self, callback) -> None:
        if self._settle_id is not None:
            with contextlib.suppress(Exception):
                self._scheduler.remove_timeout(self._settle_id)
            self._settle_id = None
        gen = self.gen

        def _fire() -> bool:
            self._settle_id = None
            if self.active and gen == self.gen:
                callback()
            return False

        self._settle_id = self._scheduler.add_timeout(int(DISCONNECT_SETTLE_SECONDS * 1000), _fire)

    def advance(
        self,
        reason: str,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Marks the current attempt as failed and moves to the next server."""
        if not self.active:
            return
        current = self.current
        if current:
            mark_state = getattr(self._win, "set_connection_attempt_state", None)
            if callable(mark_state):
                mark_state(current, "failed")
            self.failures.append((current, reason))
            self._complete_active_attempt(
                reason,
                error_code=error_code or reason,
                error_message=error_message or reason,
            )
            logger.info("Cascade skip %s (%s)", current, reason)

        self._disarm_timers()
        self.index += 1
        self.phase = CascadePhase.SETTLING
        self.expect_disconnect = True
        self._win.manual_disconnect = True

        try:
            cm = self._win.CM()
            if cm is not None and cm.status():
                cm.disconnect()
                self._arm_settle(self._try_current_server)
                return
        except Exception as exc:
            logger.debug("Cascade disconnect on advance: %s", exc)

        self._arm_settle(self._try_current_server)

    def finish(self, phase: CascadePhase, restore_connect_ui: bool = True) -> None:
        """Terminates the cascade in ``phase`` and restores the UI."""
        gen_was = self.gen
        self._disarm_timers()
        was_preparing = self.phase == CascadePhase.PREPARING
        self.active = False
        self.phase = phase
        self.expect_disconnect = False
        self.auto_cascade_after_test = False

        win = self._win
        self._set_controls_locked(False)
        self._set_fastest_button_cancel(False)
        if phase != CascadePhase.SUCCEEDED and hasattr(win, "connect_btn"):
            win.connect_btn.set_label(_("Connect"))
            win.connect_btn.remove_css_class("destructive-action")
            win.connect_btn.add_css_class("suggested-action")
        if hasattr(win, "cascade_spinner"):
            win.cascade_spinner.stop()

        if phase == CascadePhase.SUCCEEDED:
            self._complete_active_attempt("success")
            name = self.current or win.get_selected_config() or ""
            rtt = (win.latencies or {}).get(name)
            if rtt is not None:
                msg = _("Connected to {} ({} ms)").format(name, rtt)
            else:
                msg = _("Connected to {}").format(name)
            if hasattr(win, "cascade_title"):
                win.cascade_title.set_text(msg)
                win.cascade_meta.set_text(_("Attempt {}/{}").format(self.index + 1, max(1, len(self.queue))))
                win.cascade_banner.add_css_class("cascade-success")
                win.cascade_bar.set_fraction(1.0)
                win.cascade_revealer.set_reveal_child(False)
            win.show_toast(msg)
            self._scheduler.add_timeout_seconds(3, lambda: self._hide_banner(gen_was))
            return

        if phase == CascadePhase.CANCELLED:
            self._complete_active_attempt(
                "cancelled",
                error_code="cancelled",
                error_message="Auto-connect cancelled by the user.",
            )
            if hasattr(win, "cascade_revealer"):
                win.cascade_revealer.set_reveal_child(False)
            win.show_toast(_("Auto-connect cancelled"))
            if restore_connect_ui and not was_preparing:
                try:
                    cm = win.CM()
                    if cm is not None and cm.status():
                        win.manual_disconnect = True
                        cm.disconnect()
                except Exception:
                    pass
            return

        self._complete_active_attempt(
            "backend_error",
            error_code="no_usable_candidate",
            error_message="No usable backend or candidate remained.",
        )
        summary = self.attempt_summary()
        n_fail = summary["timeouts"] + summary["handshake_failures"] + summary["backend_errors"]
        if hasattr(win, "cascade_title"):
            win.cascade_title.set_text(_("Could not connect to any server in the list"))
            win.cascade_meta.set_text(
                _("{} failed · {}/{} tried").format(n_fail, summary["attempts"], summary["candidates"])
            )
            win.cascade_banner.add_css_class("cascade-fail")
            win.cascade_bar.set_fraction(1.0)
            win.cascade_revealer.set_reveal_child(False)
        self._scheduler.add_timeout_seconds(5, lambda: self._hide_banner(gen_was))

    def _complete_active_attempt(
        self,
        result: str,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Close the current attempt exactly once for accurate reporting."""
        attempt = self._active_attempt
        if attempt is None or attempt.finished_at is not None:
            return
        attempt.finished_at = datetime.now(timezone.utc)
        attempt.elapsed_seconds = max(0.0, self._now() - (self.deadline - attempt.timeout_seconds))
        attempt.result = result
        attempt.error_code = error_code
        attempt.error_message = error_message

    def _hide_banner(self, gen: int) -> bool:
        if not self.active and hasattr(self._win, "cascade_revealer"):
            self._win.cascade_revealer.set_reveal_child(False)
            self._win.cascade_banner.remove_css_class("cascade-success")
            self._win.cascade_banner.remove_css_class("cascade-fail")
        return False

    def _set_fastest_button_cancel(self, cancel: bool) -> None:
        win = self._win
        if not hasattr(win, "fastest_btn"):
            return
        if cancel:
            win.fastest_btn.set_label(_("Cancel"))
            win.fastest_btn.remove_css_class("suggested-action")
            win.fastest_btn.add_css_class("destructive-action")
            win.fastest_btn.set_tooltip_text(_("Cancel auto-connect"))
        else:
            win.fastest_btn.set_label(_("Connect Fastest"))
            win.fastest_btn.remove_css_class("destructive-action")
            win.fastest_btn.remove_css_class("suggested-action")
            win.fastest_btn.set_tooltip_text(
                _(
                    "Try all eligible servers in measured-latency order. "
                    "If the handshake times out or fails, automatically try the next one."
                )
            )

    def _set_controls_locked(self, locked: bool) -> None:
        widgets = [
            getattr(self._win, "speed_test_btn", None),
            getattr(self._win, "sort_btn", None),
            getattr(self._win, "search_entry", None),
            getattr(self._win, "filter_dropdown", None),
            getattr(self._win, "proto_dropdown", None),
            getattr(self._win, "connect_btn", None),
        ]
        for widget in widgets:
            if widget is not None:
                widget.set_sensitive(not locked)
