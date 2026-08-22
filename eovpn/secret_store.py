"""
Secure credential storage for eOVPN-Pro.
ذخیره‌سازی امن اطلاعات احراز هویت eOVPN-Pro.

Passwords are kept in Secret Service whenever available and mirrored in a
process-local, volatile cache so a locked or unavailable keyring does not make
the current session unusable. Passwords are never written to GSettings.
رمزها در صورت دسترسی در Secret Service نگهداری می‌شوند و یک نسخه موقت نیز در
حافظه همان پردازه قرار می‌گیرد تا قفل یا قطعی Keyring نشست جاری را مختل نکند.
رمز عبور هرگز در GSettings نوشته نمی‌شود.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

import gi

gi.require_version("Secret", "1")
from gi.repository import Secret

from .constants import LEGACY_SECRET_SCHEMA_IDS, SECRET_SCHEMA_ID

logger = logging.getLogger(__name__)

SecretCallback = Callable[[bool, str | None], None]


class SecretStore:
    """
    Secret Service adapter with a volatile per-username fallback cache.
    مبدل Secret Service همراه با کش موقت و تفکیک‌شده بر اساس نام کاربری.
    """

    def __init__(self) -> None:
        self.schema = self._new_schema(SECRET_SCHEMA_ID)
        self.legacy_schemas = tuple(
            self._new_schema(schema_id) for schema_id in LEGACY_SECRET_SCHEMA_IDS
        )
        self._session: dict[str, str] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _new_schema(schema_id: str) -> Secret.Schema:
        """Creates an in-memory libsecret schema / ساخت اسکیمای درون‌حافظه‌ای libsecret."""
        return Secret.Schema.new(
            schema_id,
            Secret.SchemaFlags.NONE,
            {"username": Secret.SchemaAttributeType.STRING},
        )

    @staticmethod
    def _attributes(username: str) -> dict[str, str]:
        return {"username": username}

    def set_session(self, username: str | None, password: str | None) -> None:
        """Updates only the volatile cache / فقط کش موقت نشست را به‌روز می‌کند."""
        if not username:
            return
        with self._lock:
            if password:
                self._session[username] = password
            else:
                self._session.pop(username, None)

    def get_session(self, username: str | None) -> str | None:
        """Returns a volatile password / بازگرداندن رمز موقت نشست."""
        if not username:
            return None
        with self._lock:
            return self._session.get(username)

    def lookup(self, username: str | None) -> str | None:
        """
        Looks up a password synchronously, including legacy schemas and RAM.
        جست‌وجوی همگام رمز در اسکیمای فعلی، اسکیمای قدیمی و حافظه موقت.
        """
        if not username:
            return None

        attributes = self._attributes(username)
        schemas = (self.schema, *self.legacy_schemas)
        for schema in schemas:
            try:
                password = Secret.password_lookup_sync(schema, attributes, None)
            except Exception as exc:
                logger.debug("Secret Service lookup failed: %s", exc)
                continue
            if password:
                self.set_session(username, password)
                return password

        return self.get_session(username)

    def lookup_async(self, username: str | None, callback: SecretCallback) -> None:
        """
        Looks up a password without blocking GTK and falls back to RAM.
        جست‌وجوی غیرمسدودکننده رمز با بازگشت امن به حافظه موقت.
        """
        if not username:
            callback(False, None)
            return

        attributes = self._attributes(username)
        schemas = iter((self.schema, *self.legacy_schemas))

        def try_next() -> None:
            try:
                schema = next(schemas)
            except StopIteration:
                password = self.get_session(username)
                callback(password is not None, password)
                return

            def on_lookup(_source, result) -> None:
                try:
                    password = Secret.password_lookup_finish(result)
                except Exception as exc:
                    logger.debug("Asynchronous Secret Service lookup failed: %s", exc)
                    try_next()
                    return
                if password:
                    self.set_session(username, password)
                    callback(True, password)
                else:
                    try_next()

            try:
                Secret.password_lookup(schema, attributes, None, on_lookup)
            except Exception as exc:
                logger.debug("Could not start Secret Service lookup: %s", exc)
                try_next()

        try_next()

    def store_async(
        self,
        username: str | None,
        password: str | None,
        callback: SecretCallback | None = None,
    ) -> None:
        """
        Stores the final password once; an empty password clears the secret.
        ذخیره یک‌باره رمز نهایی؛ رمز خالی باعث حذف Secret می‌شود.
        """
        if not username:
            if callback:
                callback(False, "Username is required.")
            return
        if not password:
            self.clear_async(username, callback)
            return

        self.set_session(username, password)
        attributes = self._attributes(username)

        def on_stored(_source, result) -> None:
            try:
                success = bool(Secret.password_store_finish(result))
                error = None if success else "Secret Service declined the request."
            except Exception as exc:
                success = False
                error = str(exc)
                logger.info("Secret Service unavailable; password remains in RAM: %s", exc)
            if callback:
                callback(success, error)

        try:
            Secret.password_store(
                self.schema,
                attributes,
                Secret.COLLECTION_DEFAULT,
                "eOVPN Pro VPN password",
                password,
                None,
                on_stored,
            )
        except Exception as exc:
            logger.info("Could not start Secret Service storage; password remains in RAM: %s", exc)
            if callback:
                callback(False, str(exc))

    def clear_async(
        self,
        username: str | None,
        callback: SecretCallback | None = None,
    ) -> None:
        """
        Removes current and legacy keyring entries for one username.
        حذف رکوردهای فعلی و قدیمی Keyring برای یک نام کاربری.
        """
        if not username:
            if callback:
                callback(True, None)
            return

        self.set_session(username, None)
        attributes = self._attributes(username)
        schemas = iter((self.schema, *self.legacy_schemas))
        errors: list[str] = []

        def clear_next() -> None:
            try:
                schema = next(schemas)
            except StopIteration:
                if callback:
                    callback(not errors, "; ".join(errors) if errors else None)
                return

            def on_cleared(_source, result) -> None:
                try:
                    Secret.password_clear_finish(result)
                except Exception as exc:
                    errors.append(str(exc))
                    logger.debug("Secret Service clear failed: %s", exc)
                clear_next()

            try:
                Secret.password_clear(schema, attributes, None, on_cleared)
            except Exception as exc:
                errors.append(str(exc))
                logger.debug("Could not start Secret Service clear: %s", exc)
                clear_next()

        clear_next()

    def clear_session(self) -> None:
        """Erases all process-local passwords / پاک‌کردن همه رمزهای موقت پردازه."""
        with self._lock:
            self._session.clear()


DEFAULT_SECRET_STORE = SecretStore()
