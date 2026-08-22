// clang-format off
/*
 * eOVPN-Pro scoped OpenVPN 3 Linux binding.
 * بایندینگ محدودشده OpenVPN 3 Linux برای eOVPN-Pro.
 *
 * The binding keeps exactly one explicit session proxy and uses finite D-Bus
 * timeouts. It never enumerates or disconnects sessions owned by other tools.
 * این بایندینگ فقط یک نشست صریح را نگه می‌دارد، تایم‌اوت محدود دارد و
 * هرگز
 * نشست‌های متعلق به ابزارهای دیگر را فهرست یا قطع
 * نمی‌کند.
 */
// clang-format on

#define G_LOG_DOMAIN "eovpn"
#define EOVPN_DBUS_TIMEOUT_MS 10000

#include <gio/gio.h>
#include <glib.h>
#include <stdbool.h>

#include "enums.h"
#include "openvpn3.h"

static GDBusProxy *unique_session = NULL;

static GDBusProxy *
new_proxy (const char *bus_name,
           const char *object_path,
           const char *interface_name,
           GError **error)
{
    return g_dbus_proxy_new_for_bus_sync (G_BUS_TYPE_SYSTEM,
                                          G_DBUS_PROXY_FLAGS_NONE,
                                          NULL,
                                          bus_name,
                                          object_path,
                                          interface_name,
                                          NULL,
                                          error);
}

static GVariant *
call_proxy (GDBusProxy *proxy,
            const char *method,
            GVariant *parameters,
            GError **error)
{
    if (proxy == NULL)
        return NULL;
    return g_dbus_proxy_call_sync (proxy,
                                   method,
                                   parameters,
                                   G_DBUS_CALL_FLAGS_NONE,
                                   EOVPN_DBUS_TIMEOUT_MS,
                                   NULL,
                                   error);
}

static gboolean
log_error (const char *operation, GError *error)
{
    if (error == NULL)
        return FALSE;
    g_warning ("OpenVPN 3 %s failed: %s", operation, error->message);
    g_error_free (error);
    return TRUE;
}

int
get_specific_connection_status (char *session_path)
{
    GDBusProxy *proxy;
    GVariant *reply;
    GVariant *status_value = NULL;
    GError *error = NULL;
    guint32 major = 0;
    guint32 minor = 0;
    char *status_text = NULL;
    gboolean connected = FALSE;

    if (session_path == NULL)
        return FALSE;

    proxy = new_proxy ("net.openvpn.v3.sessions",
                       session_path,
                       "org.freedesktop.DBus.Properties",
                       &error);
    if (log_error ("status proxy", error))
        return FALSE;

    reply =
        call_proxy (proxy,
                    "Get",
                    g_variant_new ("(ss)", "net.openvpn.v3.sessions", "status"),
                    &error);
    g_object_unref (proxy);
    if (log_error ("status lookup", error) || reply == NULL)
        return FALSE;

    g_variant_get (reply, "(v)", &status_value);
    g_variant_get (status_value, "(uus)", &major, &minor, &status_text);
    connected = major == MAJOR_CONNECTION &&
                (minor == MINOR_CONN_CONNECTED || minor == MINOR_CONN_PAUSED);

    g_free (status_text);
    g_variant_unref (status_value);
    g_variant_unref (reply);
    return connected;
}

char *
get_version (void)
{
    GDBusProxy *proxy;
    GVariant *reply;
    GVariant *version_value = NULL;
    const char *version_text = NULL;
    GError *error = NULL;
    char *result = NULL;

    proxy = new_proxy ("net.openvpn.v3.configuration",
                       "/net/openvpn/v3/configuration",
                       "org.freedesktop.DBus.Properties",
                       &error);
    if (log_error ("version proxy", error))
        return NULL;

    reply = call_proxy (
        proxy,
        "Get",
        g_variant_new ("(ss)", "net.openvpn.v3.configuration", "version"),
        &error);
    g_object_unref (proxy);
    if (log_error ("version lookup", error) || reply == NULL)
        return NULL;

    g_variant_get (reply, "(v)", &version_value);
    g_variant_get (version_value, "&s", &version_text);
    result = version_text != NULL ? g_strdup (version_text) : NULL;
    g_variant_unref (version_value);
    g_variant_unref (reply);
    return result;
}

char *
import_config (char *name, char *config_str)
{
    GDBusProxy *proxy;
    GVariant *reply;
    GError *error = NULL;
    const char *object_path = NULL;
    char *result = NULL;

    if (name == NULL || config_str == NULL)
        return NULL;

    proxy = new_proxy ("net.openvpn.v3.configuration",
                       "/net/openvpn/v3/configuration",
                       "net.openvpn.v3.configuration",
                       &error);
    if (log_error ("configuration proxy", error))
        return NULL;

    /* single_use=true and persistent=false keep the profile memory-only.
     * single_use=true و persistent=false پروفایل را فقط در حافظه نگه
     * می‌دارند. */
    reply = call_proxy (proxy,
                        "net.openvpn.v3.configuration.Import",
                        g_variant_new ("(ssbb)", name, config_str, TRUE, FALSE),
                        &error);
    g_object_unref (proxy);
    if (log_error ("configuration import", error) || reply == NULL)
        return NULL;

    g_variant_get (reply, "(&o)", &object_path);
    result = object_path != NULL ? g_strdup (object_path) : NULL;
    g_variant_unref (reply);
    return result;
}

char *
prepare_tunnel (char *config_object)
{
    GDBusProxy *proxy;
    GVariant *reply;
    GError *error = NULL;
    const char *object_path = NULL;
    char *result = NULL;

    if (config_object == NULL)
        return NULL;

    proxy = new_proxy ("net.openvpn.v3.sessions",
                       "/net/openvpn/v3/sessions",
                       "net.openvpn.v3.sessions",
                       &error);
    if (log_error ("session manager proxy", error))
        return NULL;

    reply = call_proxy (proxy,
                        "net.openvpn.v3.sessions.NewTunnel",
                        g_variant_new ("(o)", config_object),
                        &error);
    g_object_unref (proxy);
    if (log_error ("tunnel preparation", error) || reply == NULL)
        return NULL;

    g_variant_get (reply, "(&o)", &object_path);
    result = object_path != NULL ? g_strdup (object_path) : NULL;
    g_variant_unref (reply);
    return result;
}

void
init_unique_session (char *session_object)
{
    GDBusProxy *proxy;
    GError *error = NULL;

    if (session_object == NULL)
        return;
    proxy = new_proxy ("net.openvpn.v3.sessions",
                       session_object,
                       "net.openvpn.v3.sessions",
                       &error);
    if (log_error ("session proxy", error))
        return;
    g_clear_object (&unique_session);
    unique_session = proxy;
}

int
set_dco (char *session_object, int state)
{
    GDBusProxy *proxy;
    GVariant *reply;
    GError *error = NULL;

    if (session_object == NULL)
        return FALSE;
    proxy = new_proxy ("net.openvpn.v3.sessions",
                       session_object,
                       "org.freedesktop.DBus.Properties",
                       &error);
    if (log_error ("DCO proxy", error))
        return FALSE;

    reply = call_proxy (proxy,
                        "Set",
                        g_variant_new ("(ssv)",
                                       "net.openvpn.v3.sessions",
                                       "dco",
                                       g_variant_new_boolean (state != 0)),
                        &error);
    g_object_unref (proxy);
    if (log_error ("DCO update", error) || reply == NULL)
        return FALSE;
    g_variant_unref (reply);
    return TRUE;
}

char *
is_ready_to_connect (void)
{
    GVariant *reply;
    GError *error = NULL;
    char *message;

    if (unique_session == NULL)
        return g_strdup ("Session is not initialized");
    reply = call_proxy (unique_session,
                        "net.openvpn.v3.sessions.Ready",
                        g_variant_new ("()"),
                        &error);
    if (error != NULL)
        {
            message = g_strdup (error->message);
            g_error_free (error);
            return message;
        }
    if (reply != NULL)
        g_variant_unref (reply);
    return NULL;
}

int
send_auth (char *session_object, int type, int group, int id, char *value)
{
    GVariant *reply;
    GError *error = NULL;

    if (session_object == NULL || value == NULL)
        return FALSE;
    init_unique_session (session_object);
    if (unique_session == NULL)
        return FALSE;

    reply = call_proxy (unique_session,
                        "UserInputProvide",
                        g_variant_new ("(uuus)", type, group, id, value),
                        &error);
    if (log_error ("credential submission", error) || reply == NULL)
        return FALSE;
    g_variant_unref (reply);
    return TRUE;
}

int
connect_vpn (void)
{
    GVariant *reply;
    GError *error = NULL;

    if (unique_session == NULL)
        return FALSE;
    reply =
        call_proxy (unique_session, "Connect", g_variant_new ("()"), &error);
    if (log_error ("connect", error) || reply == NULL)
        return FALSE;
    g_variant_unref (reply);
    return TRUE;
}

int
disconnect_vpn (void)
{
    GVariant *reply;
    GError *error = NULL;
    gboolean success;

    if (unique_session == NULL)
        return FALSE;
    reply =
        call_proxy (unique_session, "Disconnect", g_variant_new ("()"), &error);
    success = error == NULL && reply != NULL;
    log_error ("disconnect", error);
    if (reply != NULL)
        g_variant_unref (reply);
    g_clear_object (&unique_session);
    return success;
}

int
pause_vpn (char *reason)
{
    GVariant *reply;
    GError *error = NULL;

    if (unique_session == NULL || reason == NULL)
        return FALSE;
    reply = call_proxy (
        unique_session, "Pause", g_variant_new ("(s)", reason), &error);
    if (log_error ("pause", error) || reply == NULL)
        return FALSE;
    g_variant_unref (reply);
    return TRUE;
}

int
resume_vpn (void)
{
    GVariant *reply;
    GError *error = NULL;

    if (unique_session == NULL)
        return FALSE;
    reply = call_proxy (unique_session, "Resume", g_variant_new ("()"), &error);
    if (log_error ("resume", error) || reply == NULL)
        return FALSE;
    g_variant_unref (reply);
    return TRUE;
}

char *
p_get_version (void)
{
    return get_version ();
}

void
eovpn_free (char *value)
{
    g_free (value);
}
