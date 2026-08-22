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
    cascade_banner_meta,
    cascade_progress_fraction,
    cascade_reason_label,
    cascade_remaining_seconds,
)
from .events import ConnectionEvent, ConnectionEventKind
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
    def select_server_by_name(self, filename: str) -> bool: ...
    def protocols_for(self, filename: str) -> frozenset[str]: ...
    def trigger_speed_test(self) -> None: ...
    def show_toast(self, message: str, timeout: int = 2) -> None: ...


class CascadeController:
    """
    Drives the connect-to-fastest cascade with an adaptive handshake timeout.

    هدایت اتصال آبشاری به سریع‌ترین سرور با تایم‌اوت تطبیقی دست‌دهی.
    """

    def __init__(self, host: CascadeHost, scheduler: TimerScheduler | None = None) -> None:
        self._win = host
        self._scheduler = scheduler if scheduler is not None else create_default_scheduler()

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
        self.expect_disconnect = False
        self.disconnect_retries = 0

        # Scheduler source ids / شناسه‌های زمان‌بند
        self._timeout_id: Any = None
        self._tick_id: Any = None
        self._settle_id: Any = None

    # ------------------------------------------------------------------
    # Public entry points / نقاط ورود عمومی
    # ------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        """True while a cascade (or its pre-connect speed test) is running."""
        return self.active or self.auto_cascade_after_test

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
        visible = collect_visible_filenames(getattr(win, "list_box", None))
        if not visible:
            win.show_toast(_("No servers match the current filters."))
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

    def start_from_visible_list(self) -> None:
        """Builds the attempt queue from the visible list and begins walking it."""
        win = self._win
        visible = collect_visible_filenames(getattr(win, "list_box", None))
        queue = build_cascade_queue(visible, win.latencies, skip_unreachable=True)
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

        if len(visible) > MAX_CASCADE_CANDIDATES:
            win.show_toast(
                _("Auto-connect will try the first {} of {} visible servers.").format(
                    len(queue), len(visible)
                )
            )

        self._begin(queue)

    def cancel(self, user: bool = True) -> None:
        """Aborts a running cascade or the pre-connect speed test."""
        if not self.busy:
            return
        logger.info("Cascade cancelled (user=%s)", user)
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
        if event.kind == ConnectionEventKind.CONNECTED:
            self._disarm_timers()
            self.expect_disconnect = False
            self.finish(CascadePhase.SUCCEEDED, restore_connect_ui=False)
            return False

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
            self.advance(reason)
            return True

        return True

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
            win.cascade_revealer.set_reveal_child(True)
        self._set_fastest_button_cancel(True)

    def _begin(self, queue: list[str]) -> None:
        self.gen += 1
        self.active = True
        self.queue = list(queue)
        self.index = 0
        self.failures = []
        self.expect_disconnect = False
        self.disconnect_retries = 0
        self.phase = CascadePhase.CONNECTING
        self.current = None
        win = self._win
        win.manual_disconnect = False

        self._set_controls_locked(True)
        self._set_fastest_button_cancel(True)
        if hasattr(win, "cascade_banner"):
            win.cascade_banner.remove_css_class("cascade-success")
            win.cascade_banner.remove_css_class("cascade-fail")
            win.cascade_spinner.start()
            win.cascade_revealer.set_reveal_child(True)

        win.show_toast(_("Auto-connect started — {} server(s) in the current list.").format(len(self.queue)))

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
        self.deadline = time.monotonic() + timeout
        self.expect_disconnect = False
        win.manual_disconnect = False

        win.select_server_by_name(filename)
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
                self.advance("missing")
                return False
            manager.connect(path)
        except Exception as exc:
            logger.error("Cascade connect error for %s: %s", filename, exc)
            self.advance("error")
        return False

    def _update_banner(self, status: str | None = None) -> None:
        win = self._win
        if not hasattr(win, "cascade_title"):
            return
        total = max(1, len(self.queue))
        idx = min(self.index + 1, total)
        name = self.current or ""
        rtt = (win.latencies or {}).get(name)
        proto = format_proto_badge(win.protocols_for(name)) if name else ""
        remaining = cascade_remaining_seconds(self.deadline, time.monotonic())

        if status:
            win.cascade_title.set_text(status)
        else:
            extras = [part for part in (proto, f"{rtt} ms" if rtt is not None else "") if part]
            suffix = f"  ·  {' · '.join(extras)}" if extras else ""
            win.cascade_title.set_text(_("Trying {}{}").format(name, suffix))
        win.cascade_meta.set_text(cascade_banner_meta(idx - 1, total, remaining))

        attempt_timeout = compute_attempt_timeout(rtt)
        elapsed = attempt_timeout - max(0.0, self.deadline - time.monotonic())
        overall = cascade_progress_fraction(self.index, total, elapsed, attempt_timeout)
        win.cascade_bar.set_fraction(overall)
        if hasattr(win, "progress_bar") and self.phase == CascadePhase.CONNECTING:
            # Keep the historical 0.92 ceiling so the bar never looks "done"
            # while attempts are still running.
            # حفظ سقف تاریخی 0.92 تا نوار هرگز هنگام تلاش‌های در جریان «کامل» دیده نشود.
            win.progress_bar.set_fraction(
                min(
                    0.92,
                    cascade_progress_fraction(self.index, total, 0.4 * attempt_timeout, attempt_timeout),
                )
            )

    def _arm_timeout_and_ticks(self) -> None:
        self._disarm_timers(keep_settle=False)
        remaining_ms = max(250, int((self.deadline - time.monotonic()) * 1000))
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
        self._update_banner()
        return True

    def _on_timeout(self, gen: int) -> bool:
        self._timeout_id = None
        if not self.active or gen != self.gen:
            return False
        if self._user_is_busy():
            self.deadline = time.monotonic() + 4.0
            self._arm_timeout_and_ticks()
            return False
        try:
            cm = self._win.CM()
            if cm is not None and cm.status():
                # Handshake landed in the same tick as the timeout.
                return False
        except Exception:
            pass
        logger.info("Cascade handshake timeout on %s", self.current)
        self.advance("timeout")
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

    def advance(self, reason: str) -> None:
        """Marks the current attempt as failed and moves to the next server."""
        if not self.active:
            return
        current = self.current
        if current:
            self.failures.append((current, reason))
            logger.info("Cascade skip %s (%s)", current, reason)

        self._disarm_timers()
        self._win.show_toast(
            _("Could not connect to {} ({}) — next server…").format(
                current or "?", cascade_reason_label(reason)
            )
        )

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
        if hasattr(win, "cascade_spinner"):
            win.cascade_spinner.stop()

        if phase == CascadePhase.SUCCEEDED:
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
                win.cascade_revealer.set_reveal_child(True)
            win.show_toast(msg)
            self._scheduler.add_timeout_seconds(3, lambda: self._hide_banner(gen_was))
            return

        if phase == CascadePhase.CANCELLED:
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

        n_fail = len(self.failures)
        if hasattr(win, "cascade_title"):
            win.cascade_title.set_text(_("Could not connect to any server in the list"))
            win.cascade_meta.set_text(_("{} attempt(s) failed").format(n_fail))
            win.cascade_banner.add_css_class("cascade-fail")
            win.cascade_bar.set_fraction(1.0)
            win.cascade_revealer.set_reveal_child(True)
        win.show_toast(
            _("Auto-connect failed — no server in the current list accepted the handshake."),
            timeout=4,
        )
        self._scheduler.add_timeout_seconds(5, lambda: self._hide_banner(gen_was))

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
            win.fastest_btn.add_css_class("suggested-action")
            win.fastest_btn.set_tooltip_text(
                _(
                    "Connect to the first server in the current sorted and filtered list. "
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
