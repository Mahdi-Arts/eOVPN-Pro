/*
 * eOVPN-Pro OpenVPN 3 Linux Native C / D-Bus Binding
 * لایه بایندینگ بومی C جهت تعامل با D-Bus و سرویس OpenVPN 3 Linux
 *
 * This file is part of eOVPN-Pro.
 * این فایل بخشی از eOVPN-Pro است.
 *
 * eOVPN-Pro is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * eOVPN-Pro is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with eOVPN-Pro.  If not, see <https://www.gnu.org/licenses/>.
 */

#define G_LOG_DOMAIN "eovpn"

#include <stdio.h>
#include <stdbool.h>
#include <gio/gio.h>
#include <glib.h>
#include "openvpn3.h"
#include "enums.h"

/*
 * Every D-Bus call carries a bounded timeout to prevent a hung system service
 * from freezing the UI indefinitely.
 *
 * همه تماس‌های D-Bus مهلت محدود دارند تا هنگ هنگ سرویس سیستم باعث قفل بی‌پایان
 * رابط کاربری نشود.
 */
#define EOVPN_DBUS_TIMEOUT_MS 15000

/*
 * Session-scoped helpers. Every operation below takes the session object
 * path explicitly instead of relying on process-wide static state: the
 * binding is now thread-safe and can drive more than one tunnel session.
 *
 * توابع دارای محدوده نشست. همه عملیات‌های پایین مسیر نشست را صریحاً می‌گیرند
 * و به state سراسری پروسه تکیه نمی‌کنند؛ بایندینگ اکنون thread-safe است و
 * می‌تواند بیش از یک نشست تونل را هدایت کند.
 */

/*
 * Creates a D-Bus proxy for one session object path, or NULL with ``error``
 * set when the path is unusable.
 */
static GDBusProxy *
_session_proxy_for (const char *session_object, GError **error)
{
    if (session_object == NULL)
        return NULL;

    return g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        session_object,
        "net.openvpn.v3.sessions",
        NULL,
        error);
}

static GVariantIter *
_get_all_sessions (void)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) sessions_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        "/net/openvpn/v3/sessions",
        "net.openvpn.v3.sessions",
        NULL,
        &error);

    if (sessions_proxy == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return NULL;
    }

    g_autoptr(GVariant) available_sessions = g_dbus_proxy_call_sync (
        sessions_proxy,
        "FetchAvailableSessions",
        g_variant_new ("()"),
        G_DBUS_CALL_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS,
        NULL,
        &error);

    if (available_sessions == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return NULL;
    }

    /* The iter takes its own reference; the autoptr releases ours so this
     * polling helper no longer leaks one GVariant per call. */
    g_autoptr(GVariant) active_sessions =
        g_variant_get_child_value (available_sessions, 0);
    return g_variant_iter_new (active_sessions);
}

static gboolean
_session_status_is_connected (const gchar *path)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) sessions_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        path,
        "org.freedesktop.DBus.Properties",
        NULL,
        &error);

    if (sessions_proxy == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return false;
    }

    g_autoptr(GVariant) status = g_dbus_proxy_call_sync (
        sessions_proxy,
        "Get",
        g_variant_new ("(ss)", "net.openvpn.v3.sessions", "status"),
        G_DBUS_CALL_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS,
        NULL,
        &error);

    if (status == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return false;
    }

    GVariant *v = NULL;
    guint16 major = 0;
    guint16 minor = 0;
    gchar *status_str = NULL;

    g_variant_get (status, "(v)", &v);
    g_variant_get (v, "(uus)", &major, &minor, &status_str);
    g_debug ("OpenVPN3 Status: %u %u %s", major, minor, status_str);

    g_free (status_str);
    g_variant_unref (v);

    return (major == MAJOR_CONNECTION)
        && ((minor == MINOR_CONN_CONNECTED) || (minor == MINOR_CONN_PAUSED));
}

int
get_connection_status (void)
{
    GVariantIter *iter = _get_all_sessions ();
    gchar *path = NULL;

    if (iter == NULL)
        return -1;

    while (g_variant_iter_next (iter, "o", &path))
    {
        gboolean connected = _session_status_is_connected (path);
        g_free (path);
        if (connected)
        {
            g_variant_iter_free (iter);
            return true;
        }
    }

    g_variant_iter_free (iter);
    return false;
}

void
disconnect_all_sessions (void)
{
    GVariantIter *iter = _get_all_sessions ();
    gchar *path = NULL;

    if (iter == NULL)
        return;

    while (g_variant_iter_next (iter, "o", &path))
    {
        if (_session_status_is_connected (path))
        {
            g_autoptr(GError) error = NULL;
            g_autoptr(GDBusProxy) proxy = g_dbus_proxy_new_for_bus_sync (
                G_BUS_TYPE_SYSTEM,
                G_DBUS_PROXY_FLAGS_NONE,
                NULL,
                "net.openvpn.v3.sessions",
                path,
                "net.openvpn.v3.sessions",
                NULL,
                &error);

            if (proxy != NULL && error == NULL)
            {
                g_dbus_proxy_call_sync (
                    proxy, "Disconnect", g_variant_new ("()"),
                    G_DBUS_PROXY_FLAGS_NONE, EOVPN_DBUS_TIMEOUT_MS, NULL, &error);
                g_debug ("%s disconnected!", path);
            }

            if (error != NULL)
                g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        }
        g_free (path);
    }

    g_variant_iter_free (iter);
}

int
get_specific_connection_status (char *session_path)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) sessions_proxy = NULL;
    g_autoptr(GVariant) status = NULL;
    GVariant *v = NULL;
    guint16 major = 0;
    guint16 minor = 0;
    gchar *status_str = NULL;
    gboolean connected;

    if (session_path == NULL)
        return false;

    sessions_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        session_path,
        "org.freedesktop.DBus.Properties",
        NULL,
        &error);

    if (sessions_proxy == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return false;
    }

    status = g_dbus_proxy_call_sync (
        sessions_proxy,
        "Get",
        g_variant_new ("(ss)", "net.openvpn.v3.sessions", "status"),
        G_DBUS_CALL_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS,
        NULL,
        &error);

    if (status == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return false;
    }

    g_variant_get (status, "(v)", &v);
    g_variant_get (v, "(uus)", &major, &minor, &status_str);

    connected = (major == MAJOR_CONNECTION && minor == MINOR_CONN_CONNECTED);
    g_free (status_str);
    g_variant_unref (v);

    return connected;
}

char *
get_version (void)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.configuration",
        "/net/openvpn/v3/configuration",
        "org.freedesktop.DBus.Properties",
        NULL,
        &error);

    if (proxy == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return NULL;
    }

    g_autoptr(GVariant) version = g_dbus_proxy_call_sync (
        proxy,
        "Get",
        g_variant_new ("(ss)", "net.openvpn.v3.configuration", "version"),
        G_DBUS_CALL_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS,
        NULL,
        &error);

    if (version == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return NULL;
    }

    GVariant *version_v = NULL;
    const gchar *version_str = NULL;
    g_variant_get (version, "(v)", &version_v);
    g_variant_get (version_v, "s", &version_str);
    char *result = g_strdup (version_str);
    g_variant_unref (version_v);
    return result;
}

char *
import_config (char *name, char *config_str)
{
    if (name == NULL || config_str == NULL)
        return NULL;

    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) import_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.configuration",
        "/net/openvpn/v3/configuration",
        "net.openvpn.v3.configuration",
        NULL,
        &error);

    if (import_proxy == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return NULL;
    }

    GVariant *params = g_variant_new ("(ssbb)", name, config_str, TRUE, FALSE);
    g_autoptr(GVariant) result = g_dbus_proxy_call_sync (
        import_proxy,
        "net.openvpn.v3.configuration.Import",
        params,
        G_DBUS_CALL_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS,
        NULL,
        &error);

    if (result == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return NULL;
    }

    const gchar *config_object = NULL;
    g_variant_get (result, "(o)", &config_object);
    return g_strdup (config_object);
}

char *
prepare_tunnel (char *config_object)
{
    if (config_object == NULL)
        return NULL;

    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) sessions_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        "/net/openvpn/v3/sessions",
        "net.openvpn.v3.sessions",
        NULL,
        &error);

    if (sessions_proxy == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return NULL;
    }

    GVariant *params = g_variant_new ("(o)", (gchar *) config_object);
    g_autoptr(GVariant) result = g_dbus_proxy_call_sync (
        sessions_proxy,
        "NewTunnel",
        params,
        G_DBUS_CALL_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS,
        NULL,
        &error);

    if (result == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return NULL;
    }

    const gchar *session_object = NULL;
    g_variant_get (result, "(o)", &session_object);
    return g_strdup (session_object);
}

/*
 * Session-scoped operations. Each function takes the session object path
 * explicitly instead of relying on process-wide static state, so the binding
 * is thread-safe and can drive more than one tunnel session at a time.
 *
 * عملیات‌های دارای محدوده نشست. هر تابع مسیر نشست را صریحاً می‌گیرد و به
 * وضعیت سراسری پروسه تکیه نمی‌کند؛ بنابراین بایندینگ thread-safe است و
 * می‌تواند بیش از یک نشست تونل را همزمان هدایت کند.
 */

void
set_log_forward (char *session_object)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) session = _session_proxy_for (session_object, &error);

    if (session == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return;
    }

    g_dbus_proxy_call_sync (
        session,
        "net.openvpn.v3.sessions.LogForward",
        g_variant_new ("(b)", true),
        G_DBUS_PROXY_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS,
        NULL,
        &error);

    if (error != NULL)
        g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
}

char *
is_ready_to_connect (char *session_object)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) session = NULL;

    if (session_object == NULL)
        return g_strdup ("Session not initialized");

    session = _session_proxy_for (session_object, &error);
    if (session == NULL || error != NULL)
    {
        if (error != NULL)
            return g_strdup (error->message);
        return g_strdup ("Session proxy unavailable");
    }

    g_dbus_proxy_call_sync (
        session,
        "net.openvpn.v3.sessions.Ready",
        NULL,
        G_DBUS_PROXY_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS,
        NULL,
        &error);

    if (error != NULL)
        return g_strdup (error->message);

    return NULL;
}

void
send_auth (char *session_object, int type, int group, int id, char *value)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) session = NULL;
    GVariant *params = NULL;

    if (session_object == NULL || value == NULL)
        return;

    session = _session_proxy_for (session_object, &error);
    if (session == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return;
    }

    params = g_variant_new ("(uuus)", type, group, id, value);
    g_dbus_proxy_call_sync (
        session, "UserInputProvide", params, G_DBUS_PROXY_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS, NULL, &error);

    if (error != NULL)
        g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
}

void
connect_vpn (char *session_object)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) session = _session_proxy_for (session_object, &error);

    if (session == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return;
    }

    g_dbus_proxy_call_sync (
        session, "Connect", g_variant_new ("()"), G_DBUS_PROXY_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS, NULL, &error);

    if (error != NULL)
        g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
}

void
disconnect_vpn (char *session_object)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) session = _session_proxy_for (session_object, &error);

    if (session == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return;
    }

    g_dbus_proxy_call_sync (
        session, "Disconnect", g_variant_new ("()"), G_DBUS_PROXY_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS, NULL, &error);

    if (error != NULL)
        g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
}

void
pause_vpn (char *session_object, char *reason)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) session = NULL;

    if (session_object == NULL || reason == NULL)
        return;

    session = _session_proxy_for (session_object, &error);
    if (session == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return;
    }

    g_dbus_proxy_call_sync (
        session, "Pause", g_variant_new ("(s)", reason),
        G_DBUS_PROXY_FLAGS_NONE, EOVPN_DBUS_TIMEOUT_MS, NULL, &error);

    if (error != NULL)
        g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
}

void
resume_vpn (char *session_object)
{
    g_autoptr(GError) error = NULL;
    g_autoptr(GDBusProxy) session = _session_proxy_for (session_object, &error);

    if (session == NULL || error != NULL)
    {
        if (error != NULL)
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
        return;
    }

    g_dbus_proxy_call_sync (
        session, "Resume", g_variant_new ("()"), G_DBUS_PROXY_FLAGS_NONE,
        EOVPN_DBUS_TIMEOUT_MS, NULL, &error);

    if (error != NULL)
        g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
}

char *
p_get_version (void)
{
    for (int max_tries = 6; max_tries != 0; max_tries--)
    {
        char *ver = get_version ();
        if (ver != NULL)
            return ver;
    }
    return NULL;
}

int
p_get_connection_status (void)
{
    for (int max_tries = 6; max_tries != 0; max_tries--)
    {
        int status = get_connection_status ();
        if (status != -1)
            return status;
    }
    return false;
}
