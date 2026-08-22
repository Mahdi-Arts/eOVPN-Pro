/*
 * eOVPN-Pro OpenVPN 3 Linux Native C / D-Bus Binding
 * لایه بایندینگ بومی C جهت تعامل با D-Bus و سرویس OpenVPN 3 Linux در eOVPN-Pro
 */

#define G_LOG_DOMAIN "eovpn"

#include <stdio.h>
#include <stdbool.h>
#include <gio/gio.h>
#include <glib.h>
#include "openvpn3.h"
#include "enums.h"

static GDBusProxy *UniqueSession = NULL;

GDBusProxy *
_get_session_proxy (void)
{
    return UniqueSession;
}

GVariantIter *
_get_all_sessions (void)
{
    GError *error = NULL;
    GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        "/net/openvpn/v3/sessions",
        "net.openvpn.v3.sessions",
        NULL,
        &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return NULL;
        }

    error = NULL;
    GVariant *available_sessions = g_dbus_proxy_call_sync (
        sessions_proxy,
        "FetchAvailableSessions",
        g_variant_new ("()"),
        G_DBUS_CALL_FLAGS_NONE,
        -1,
        NULL,
        &error);

    g_object_unref (sessions_proxy);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return NULL;
        }

    GVariant *active_sessions = g_variant_get_child_value (available_sessions, 0);
    GVariantIter *iter = g_variant_iter_new (active_sessions);
    g_variant_unref (active_sessions);
    g_variant_unref (available_sessions);
    return iter;
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
            GError *error = NULL;
            GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync (
                G_BUS_TYPE_SYSTEM,
                G_DBUS_PROXY_FLAGS_NONE,
                NULL,
                "net.openvpn.v3.sessions",
                path,
                "org.freedesktop.DBus.Properties",
                NULL,
                &error);
            g_free (path);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_error_free (error);
                    continue;
                }

            error = NULL;
            GVariant *status = g_dbus_proxy_call_sync (
                sessions_proxy,
                "Get",
                g_variant_new ("(ss)", "net.openvpn.v3.sessions", "status"),
                G_DBUS_CALL_FLAGS_NONE,
                -1,
                NULL,
                &error);

            g_object_unref (sessions_proxy);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_error_free (error);
                    continue;
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
            g_variant_unref (status);

            if ((major == MAJOR_CONNECTION) &&
                ((minor == MINOR_CONN_CONNECTED) || (minor == MINOR_CONN_PAUSED)))
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
            GError *error = NULL;
            GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync (
                G_BUS_TYPE_SYSTEM,
                G_DBUS_PROXY_FLAGS_NONE,
                NULL,
                "net.openvpn.v3.sessions",
                path,
                "org.freedesktop.DBus.Properties",
                NULL,
                &error);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_error_free (error);
                    g_free (path);
                    continue;
                }

            error = NULL;
            GVariant *status = g_dbus_proxy_call_sync (
                sessions_proxy,
                "Get",
                g_variant_new ("(ss)", "net.openvpn.v3.sessions", "status"),
                G_DBUS_CALL_FLAGS_NONE,
                -1,
                NULL,
                &error);

            g_object_unref (sessions_proxy);

            if (error != NULL)
                {
                    g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
                    g_error_free (error);
                    g_free (path);
                    continue;
                }

            GVariant *v = NULL;
            guint16 major = 0;
            guint16 minor = 0;
            gchar *status_str = NULL;

            g_variant_get (status, "(v)", &v);
            g_variant_get (v, "(uus)", &major, &minor, &status_str);

            g_free (status_str);
            g_variant_unref (v);
            g_variant_unref (status);

            if (major == MAJOR_CONNECTION)
                {
                    error = NULL;
                    GDBusProxy *proxy = g_dbus_proxy_new_for_bus_sync (
                        G_BUS_TYPE_SYSTEM,
                        G_DBUS_PROXY_FLAGS_NONE,
                        NULL,
                        "net.openvpn.v3.sessions",
                        path,
                        "net.openvpn.v3.sessions",
                        NULL,
                        &error);

                    if (proxy != NULL)
                        {
                            g_dbus_proxy_call_sync (
                                proxy, "Disconnect", g_variant_new ("()"),
                                G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
                            g_object_unref (proxy);
                            g_debug ("%s disconnected!", path);
                        }
                }
            g_free (path);
        }

    g_variant_iter_free (iter);
}

int
get_specific_connection_status (char *session_path)
{
    if (session_path == NULL)
        return false;

    GError *error = NULL;
    GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        session_path,
        "org.freedesktop.DBus.Properties",
        NULL,
        &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return false;
        }

    GVariant *status = g_dbus_proxy_call_sync (
        sessions_proxy,
        "Get",
        g_variant_new ("(ss)", "net.openvpn.v3.sessions", "status"),
        G_DBUS_CALL_FLAGS_NONE,
        -1,
        NULL,
        NULL);
    g_object_unref (sessions_proxy);

    if (status == NULL)
        return false;

    GVariant *v = NULL;
    guint16 major = 0;
    guint16 minor = 0;
    gchar *status_str = NULL;

    g_variant_get (status, "(v)", &v);
    g_variant_get (v, "(uus)", &major, &minor, &status_str);

    bool is_connected = (major == MAJOR_CONNECTION && minor == MINOR_CONN_CONNECTED);
    g_free (status_str);
    g_variant_unref (v);
    g_variant_unref (status);

    return is_connected;
}

char *
get_version (void)
{
    GError *error = NULL;
    GDBusProxy *proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.configuration",
        "/net/openvpn/v3/configuration",
        "org.freedesktop.DBus.Properties",
        NULL,
        &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return NULL;
        }

    error = NULL;
    GVariant *version = g_dbus_proxy_call_sync (
        proxy,
        "Get",
        g_variant_new ("(ss)", "net.openvpn.v3.configuration", "version"),
        G_DBUS_PROXY_FLAGS_NONE,
        -1,
        NULL,
        &error);
    g_object_unref (proxy);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return NULL;
        }

    GVariant *version_v = NULL;
    const gchar *version_str = NULL;
    g_variant_get (version, "(v)", &version_v);
    g_variant_get (version_v, "s", &version_str);
    char *result = g_strdup (version_str);
    g_variant_unref (version_v);
    g_variant_unref (version);
    return result;
}

char *
import_config (char *name, char *config_str)
{
    if (name == NULL || config_str == NULL)
        return NULL;

    GError *error = NULL;
    GDBusProxy *import_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.configuration",
        "/net/openvpn/v3/configuration",
        "net.openvpn.v3.configuration",
        NULL,
        &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return NULL;
        }

    GVariant *params = g_variant_new ("(ssbb)", name, config_str, TRUE, FALSE);
    error = NULL;
    GVariant *result = g_dbus_proxy_call_sync (
        import_proxy,
        "net.openvpn.v3.configuration.Import",
        params,
        G_DBUS_PROXY_FLAGS_NONE,
        -1,
        NULL,
        &error);
    g_object_unref (import_proxy);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return NULL;
        }

    const gchar *config_object = NULL;
    g_variant_get (result, "(o)", &config_object);
    char *ret = g_strdup (config_object);
    g_variant_unref (result);
    return ret;
}

char *
prepare_tunnel (char *config_object)
{
    if (config_object == NULL)
        return NULL;

    GError *error = NULL;
    GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        "/net/openvpn/v3/sessions",
        "net.openvpn.v3.sessions",
        NULL,
        &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return NULL;
        }

    GVariant *params = g_variant_new ("(o)", (gchar *) config_object);
    error = NULL;
    GVariant *result = g_dbus_proxy_call_sync (
        sessions_proxy,
        "net.openvpn.v3.sessions.NewTunnel",
        params,
        G_DBUS_PROXY_FLAGS_NONE,
        -1,
        NULL,
        &error);
    g_object_unref (sessions_proxy);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return NULL;
        }

    const gchar *session_object = NULL;
    g_variant_get (result, "(o)", &session_object);
    char *ret = g_strdup (session_object);
    g_variant_unref (result);
    return ret;
}

void
init_unique_session (char *session_object)
{
    if (session_object == NULL)
        return;

    GError *error = NULL;
    GDBusProxy *unique_session = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        (gchar *) session_object,
        "net.openvpn.v3.sessions",
        NULL,
        &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return;
        }

    if (UniqueSession != NULL)
        g_object_unref (UniqueSession);

    UniqueSession = unique_session;
}

void
set_dco (char *session_object, int state)
{
    if (session_object == NULL)
        return;

    GError *error = NULL;
    GVariant *params = g_variant_new (
        "(ssv)", "net.openvpn.v3.sessions", "dco", g_variant_new ("b", state));

    GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        (gchar *) session_object,
        "org.freedesktop.DBus.Properties",
        NULL,
        &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return;
        }

    g_dbus_proxy_call_sync (
        sessions_proxy, "Set", params, G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
    g_object_unref (sessions_proxy);
}

void
set_receive_log_events (char *session_object, int set_to)
{
    if (session_object == NULL)
        return;

    GError *error = NULL;
    GVariant *params = g_variant_new (
        "(ssv)", "net.openvpn.v3.sessions", "receive_log_events", g_variant_new ("b", set_to));

    GDBusProxy *sessions_proxy = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        (gchar *) session_object,
        "org.freedesktop.DBus.Properties",
        NULL,
        &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return;
        }

    g_dbus_proxy_call_sync (
        sessions_proxy, "Set", params, G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
    g_object_unref (sessions_proxy);
}

void
set_log_forward (void)
{
    if (UniqueSession == NULL)
        return;

    GError *error = NULL;
    g_dbus_proxy_call_sync (
        UniqueSession,
        "net.openvpn.v3.sessions.LogForward",
        g_variant_new ("(b)", true),
        G_DBUS_PROXY_FLAGS_NONE,
        -1,
        NULL,
        &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
        }
}

char *
is_ready_to_connect (void)
{
    if (UniqueSession == NULL)
        return g_strdup ("Session not initialized");

    GError *error = NULL;
    g_dbus_proxy_call_sync (
        UniqueSession,
        "net.openvpn.v3.sessions.Ready",
        NULL,
        G_DBUS_PROXY_FLAGS_NONE,
        -1,
        NULL,
        &error);

    if (error != NULL)
        {
            char *error_msg = g_strdup (error->message);
            g_error_free (error);
            return error_msg;
        }

    return NULL;
}

void
send_auth (char *session_object, int type, int group, int id, char *value)
{
    if (session_object == NULL || value == NULL)
        return;

    GError *error = NULL;
    GDBusProxy *unique_session = g_dbus_proxy_new_for_bus_sync (
        G_BUS_TYPE_SYSTEM,
        G_DBUS_PROXY_FLAGS_NONE,
        NULL,
        "net.openvpn.v3.sessions",
        (gchar *) session_object,
        "net.openvpn.v3.sessions",
        NULL,
        &error);

    if (error != NULL)
        {
            g_warning ("%s:%d -> %s", __FUNCTION__, __LINE__, error->message);
            g_error_free (error);
            return;
        }

    if (UniqueSession != NULL)
        g_object_unref (UniqueSession);

    UniqueSession = unique_session;

    GVariant *params = g_variant_new ("(uuus)", type, group, id, value);
    g_dbus_proxy_call_sync (
        UniqueSession, "UserInputProvide", params, G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
}

void
connect_vpn (void)
{
    if (UniqueSession == NULL)
        return;

    g_dbus_proxy_call_sync (
        UniqueSession, "Connect", g_variant_new ("()"), G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
}

void
disconnect_vpn (void)
{
    if (UniqueSession == NULL)
        return;

    g_dbus_proxy_call (
        UniqueSession, "Disconnect", g_variant_new ("()"), G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL, NULL);
    g_object_unref (UniqueSession);
    UniqueSession = NULL;
}

void
pause_vpn (char *reason)
{
    if (UniqueSession == NULL || reason == NULL)
        return;

    g_dbus_proxy_call_sync (
        UniqueSession, "Pause", g_variant_new ("(s)", reason), G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
}

void
resume_vpn (void)
{
    if (UniqueSession == NULL)
        return;

    g_dbus_proxy_call_sync (
        UniqueSession, "Resume", g_variant_new ("()"), G_DBUS_PROXY_FLAGS_NONE, -1, NULL, NULL);
}

char *
p_get_version (void)
{
    int max_tries = 6;
    while (max_tries != 0)
        {
            char *ver = get_version ();
            if (ver != NULL)
                return ver;
            max_tries--;
        }
    return NULL;
}

int
p_get_connection_status (void)
{
    int max_tries = 6;
    while (max_tries != 0)
        {
            int status = get_connection_status ();
            if (status != -1)
                return status;
            max_tries--;
        }
    return false;
}
