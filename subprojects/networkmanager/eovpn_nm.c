/*
 * eOVPN-Pro NetworkManager Native C Binding
 * لایه بایندینگ بومی زبان C برای ارتباط با NetworkManager در eOVPN-Pro
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

#include <stdbool.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <glib.h>
#include <NetworkManager.h>
#include "eovpn_nm.h"

/*
 * Hard timeout for synchronous NetworkManager operations.
 * مهلت سخت برای عملیات همزمان NetworkManager.
 */
#define EOVPN_NM_TIMEOUT_MS 15000

#define NM_OPENVPN_KEY_USERNAME "username"
#define NM_OPENVPN_KEY_PASSWORD "password"
#define NM_OPENVPN_KEY_CA "ca"
#define EOVPN_MANAGED_KEY "managed-by"
#define EOVPN_MANAGED_VALUE "eovpn-pro"
#define EOVPN_CONNECTION_ID_PREFIX "eOVPN-Pro: "

/*
 * The CFFI boundary cannot safely transport a GError object. Keep the last
 * operation error in thread-local storage so the worker thread can retrieve a
 * bounded, human-readable message immediately after a false/NULL result.
 */
static _Thread_local char *eovpn_last_error = NULL;

static void
eovpn_clear_last_error (void)
{
    g_clear_pointer (&eovpn_last_error, g_free);
}

static void
eovpn_set_last_error (const char *format, ...)
{
    va_list args;

    eovpn_clear_last_error ();
    va_start (args, format);
    eovpn_last_error = g_strdup_vprintf (format, args);
    va_end (args);
}

const char *
get_last_error (void)
{
    return eovpn_last_error;
}

typedef struct
{
    GMainLoop *loop;
    gboolean success;
    char *uuid;
    char *error;
} EovpnAsyncResult;

static void
eovpn_capture_error (EovpnAsyncResult *state, GError *error, const char *fallback)
{
    if (error != NULL)
        state->error = g_strdup (error->message);
    else if (fallback != NULL)
        state->error = g_strdup (fallback);
}

static gboolean
eovpn_nm_watchdog (gpointer user_data)
{
    g_warning ("[eOVPN] NetworkManager operation timed out after %d ms.",
               EOVPN_NM_TIMEOUT_MS);
    g_main_loop_quit ((GMainLoop *) user_data);
    return G_SOURCE_REMOVE;
}

/* libnm delivers async callbacks on the thread-default GLib context.  The
 * Python boundary invokes these operations from a worker thread, so using the
 * process-global default context races with GTK's context.  Each operation
 * therefore owns a private context for its complete client/loop lifetime. */
static GMainLoop *
eovpn_operation_loop_new (GMainContext **context_out)
{
    GMainContext *context = g_main_context_new ();
    GMainLoop *loop;

    g_main_context_push_thread_default (context);
    loop = g_main_loop_new (context, FALSE);
    *context_out = context;
    return loop;
}

static guint
eovpn_watchdog_attach (GMainContext *context, GMainLoop *loop)
{
    GSource *source = g_timeout_source_new (EOVPN_NM_TIMEOUT_MS);
    guint source_id;

    g_source_set_callback (source, eovpn_nm_watchdog, loop, NULL);
    source_id = g_source_attach (source, context);
    g_source_unref (source);
    return source_id;
}

static void
eovpn_watchdog_remove (GMainContext *context, guint source_id)
{
    GSource *source;

    if (source_id == 0)
        return;
    source = g_main_context_find_source_by_id (context, source_id);
    if (source != NULL)
        g_source_destroy (source);
}

static void
eovpn_operation_loop_free (GMainContext *context, GMainLoop *loop)
{
    if (loop != NULL)
        g_main_loop_unref (loop);
    if (context != NULL)
    {
        g_main_context_pop_thread_default (context);
        g_main_context_unref (context);
    }
}

static gboolean
eovpn_connection_is_managed (NMConnection *conn)
{
    NMSettingConnection *connection_settings;
    NMSettingVpn *vpn;
    const char *managed;
    const char *connection_id;

    if (conn == NULL)
        return false;

    connection_settings = nm_connection_get_setting_connection (conn);
    connection_id = connection_settings != NULL
        ? nm_setting_connection_get_id (connection_settings)
        : NULL;
    if (connection_id != NULL &&
        g_str_has_prefix (connection_id, EOVPN_CONNECTION_ID_PREFIX))
        return true;

    vpn = nm_connection_get_setting_vpn (conn);
    if (vpn == NULL)
        return false;

    managed = nm_setting_vpn_get_data_item (vpn, EOVPN_MANAGED_KEY);
    return managed != NULL && strcmp (managed, EOVPN_MANAGED_VALUE) == 0;
}

/*
 * Returns a duplicated UUID of the active eOVPN-managed VPN connection.
 *
 * The connection object itself is owned by NMClient and becomes invalid the
 * moment the client is released, so it must never escape this function.
 * Only the duplicated UUID string is returned (caller frees it).
 *
 * یک UUID کپی‌شده از اتصال فعال VPN متعلق به eOVPN برمی‌گرداند.
 * شیء اتصال متعلق به NMClient است و بلافاصله پس از آزادسازی client نامعتبر
 * می‌شود؛ بنابراین هرگز نباید از این تابع خارج شود. فقط رشته UUID
 * کپی‌شده بازگردانده می‌شود (فراخوان آزادش می‌کند).
 */
static char *
eovpn_get_managed_active_uuid (void)
{
    GMainContext *context = NULL;
    NMClient *client;
    const GPtrArray *arr;
    char *uuid = NULL;

    context = g_main_context_new ();
    g_main_context_push_thread_default (context);
    client = nm_client_new (NULL, NULL);
    if (client == NULL)
    {
        g_main_context_pop_thread_default (context);
        g_main_context_unref (context);
        return NULL;
    }

    arr = nm_client_get_active_connections (client);
    if (arr != NULL)
    {
        for (size_t i = 0; i < arr->len; i++)
        {
            NMActiveConnection *active = arr->pdata[i];
            NMConnection *conn = (NMConnection *) nm_active_connection_get_connection (active);

            if (eovpn_connection_is_managed (conn))
            {
                const char *conn_uuid = nm_connection_get_uuid (conn);
                uuid = conn_uuid ? g_strdup (conn_uuid) : NULL;
                break;
            }
        }
    }

    g_object_unref (client);
    g_main_context_pop_thread_default (context);
    g_main_context_unref (context);
    return uuid;
}

static void
add_cb (NMClient *client, GAsyncResult *result, EovpnAsyncResult *state)
{
    GError *err = NULL;
    NMRemoteConnection *remote = nm_client_add_connection_finish (client, result, &err);

    if (err != NULL || remote == NULL)
        eovpn_capture_error (state, err, "NetworkManager did not return the imported VPN profile.");
    else
    {
        const char *uuid = nm_connection_get_uuid (NM_CONNECTION (remote));
        state->uuid = uuid ? g_strdup (uuid) : NULL;
        state->success = state->uuid != NULL;
        if (!state->success)
            eovpn_capture_error (state, NULL, "Imported VPN profile has no UUID.");
        g_object_unref (remote);
    }

    g_clear_error (&err);
    g_main_loop_quit (state->loop);
}

char *
add_connection (char *config_name, char *username, char *password, char *ca)
{
    GMainContext *context = NULL;
    GMainLoop *loop = NULL;
    GSList *plugins = NULL;
    NMVpnPluginInfo *plugin = NULL;
    NMVpnEditorPlugin *editor = NULL;
    NMConnection *conn = NULL;
    NMSettingVpn *vpn_settings = NULL;
    NMClient *client = NULL;
    GError *err = NULL;
    GError *flags_err = NULL;
    guint watchdog_id = 0;
    EovpnAsyncResult state = {0};
    gboolean secret_flags_ok = true;

    eovpn_clear_last_error ();

    loop = eovpn_operation_loop_new (&context);
    plugins = nm_vpn_plugin_info_list_load ();

    for (GSList *iter = plugins; iter != NULL; iter = iter->next)
    {
        NMVpnPluginInfo *info = (NMVpnPluginInfo *) iter->data;
        const char *name = nm_vpn_plugin_info_get_name (info);
        if (name != NULL && strcmp ("openvpn", name) == 0)
        {
            plugin = info;
            break;
        }
    }

    if (plugin == NULL)
    {
        eovpn_set_last_error ("NetworkManager OpenVPN plugin not found on system.");
        goto cleanup;
    }

    editor = nm_vpn_plugin_info_load_editor_plugin (plugin, &err);
    if (err != NULL)
    {
        eovpn_set_last_error ("Failed to load VPN editor plugin: %s", err->message);
        g_clear_error (&err);
        goto cleanup;
    }

    conn = nm_vpn_editor_plugin_import (editor, config_name, &err);
    if (err != NULL)
    {
        eovpn_set_last_error ("Failed to import VPN config: %s", err->message);
        g_clear_error (&err);
        goto cleanup;
    }

    vpn_settings = nm_connection_get_setting_vpn (conn);
    if (vpn_settings != NULL)
    {
        if (username != NULL && strlen (username) > 0)
            nm_setting_vpn_add_data_item (vpn_settings, NM_OPENVPN_KEY_USERNAME, username);

        if (password != NULL && strlen (password) > 0)
        {
            nm_setting_vpn_add_secret (vpn_settings, NM_OPENVPN_KEY_PASSWORD, password);

            /* Keep the password agent-owned; abort if NetworkManager cannot
             * guarantee that it will not persist the secret on disk. */
            if (!nm_setting_set_secret_flags ((NMSetting *) vpn_settings,
                                              "password",
                                              NM_SETTING_SECRET_FLAG_AGENT_OWNED,
                                              &flags_err))
            {
                eovpn_set_last_error ("Refusing to add VPN profile: failed to set agent-owned "
                                      "secret flags: %s",
                                      flags_err ? flags_err->message : "unknown");
                g_clear_error (&flags_err);
                secret_flags_ok = false;
            }
        }

        if (ca != NULL && strlen (ca) > 0)
            nm_setting_vpn_add_data_item (vpn_settings, NM_OPENVPN_KEY_CA, ca);
    }

    if (!secret_flags_ok)
        goto cleanup;

    /* Do not put an application marker into VPN data: NetworkManager passes
     * that map to the OpenVPN plugin, which rejects unknown keys. Store the
     * marker in the generic connection ID instead. */
    {
        NMSettingConnection *connection_settings =
            nm_connection_get_setting_connection (conn);
        const char *source_name = g_path_get_basename (config_name);
        char *connection_id = g_strdup_printf (EOVPN_CONNECTION_ID_PREFIX "%s", source_name);
        if (connection_settings != NULL)
            g_object_set (G_OBJECT (connection_settings), "id", connection_id, NULL);
        g_free ((char *) source_name);
        g_free (connection_id);
    }

    nm_connection_normalize (conn, NULL, NULL, NULL);

    client = nm_client_new (NULL, NULL);
    if (client == NULL)
    {
        eovpn_set_last_error ("Could not create a NetworkManager client.");
        goto cleanup;
    }
    state.loop = loop;
    nm_client_add_connection_async (client, conn, TRUE, NULL, (GAsyncReadyCallback) add_cb, &state);
    watchdog_id = eovpn_watchdog_attach (context, loop);
    g_main_loop_run (loop);
    eovpn_watchdog_remove (context, watchdog_id);

    if (!state.success)
    {
        if (state.error != NULL)
            eovpn_set_last_error ("Failed to add VPN connection: %s", state.error);
        else
            eovpn_set_last_error ("Failed to add VPN connection.");
    }

cleanup:
    if (state.error != NULL)
        g_free (state.error);
    g_clear_object (&editor);
    if (plugins != NULL)
        g_slist_free_full (plugins, g_object_unref);
    g_clear_object (&client);
    eovpn_operation_loop_free (context, loop);

    return state.uuid;
}

static void
activate_cb (NMClient *client, GAsyncResult *result, EovpnAsyncResult *state)
{
    GError *err = NULL;
    NMActiveConnection *active = nm_client_activate_connection_finish (client, result, &err);
    state->success = err == NULL && active != NULL;
    if (!state->success)
        eovpn_capture_error (state, err, "NetworkManager did not activate the VPN connection.");
    g_clear_object (&active);
    g_clear_error (&err);

    g_main_loop_quit (state->loop);
}

int
activate_connection (char *uuid)
{
    GMainContext *context;
    GMainLoop *loop;
    NMClient *client;
    const GPtrArray *arr;
    NMConnection *target = NULL;
    guint watchdog_id;
    EovpnAsyncResult state = {0};

    eovpn_clear_last_error ();

    if (uuid == NULL)
    {
        eovpn_set_last_error ("Cannot activate a VPN connection without a UUID.");
        return false;
    }

    loop = eovpn_operation_loop_new (&context);
    client = nm_client_new (NULL, NULL);
    if (client == NULL)
    {
        eovpn_set_last_error ("Could not create a NetworkManager client.");
        eovpn_operation_loop_free (context, loop);
        return false;
    }
    arr = nm_client_get_connections (client);

    if (arr != NULL)
    {
        for (size_t i = 0; i < arr->len; i++)
        {
            const char *current_uuid = nm_connection_get_uuid (NM_CONNECTION (arr->pdata[i]));
            if (current_uuid != NULL && strcmp (uuid, current_uuid) == 0)
            {
                target = NM_CONNECTION (arr->pdata[i]);
                break;
            }
        }
    }

    state.loop = loop;
    if (target != NULL)
    {
        nm_client_activate_connection_async (client, target, NULL, NULL, NULL,
                                             (GAsyncReadyCallback) activate_cb, &state);
        watchdog_id = eovpn_watchdog_attach (context, loop);
        g_main_loop_run (loop);
        eovpn_watchdog_remove (context, watchdog_id);
    }

    else
        eovpn_set_last_error ("VPN connection UUID was not found in NetworkManager.");

    g_object_unref (client);
    eovpn_operation_loop_free (context, loop);
    if (!state.success && state.error != NULL)
        eovpn_set_last_error ("Failed to activate VPN connection: %s", state.error);
    g_free (state.error);
    return state.success;
}

static void
disconnect_cb (NMClient *client, GAsyncResult *result, EovpnAsyncResult *state)
{
    GError *err = NULL;
    nm_client_deactivate_connection_finish (client, result, &err);
    state->success = err == NULL;
    if (!state->success)
        eovpn_capture_error (state, err, "NetworkManager could not disconnect the VPN connection.");
    g_clear_error (&err);
    g_main_loop_quit (state->loop);
}

int
disconnect (char *uuid)
{
    GMainContext *context;
    GMainLoop *loop;
    NMClient *client;
    const GPtrArray *arr;
    NMActiveConnection *target = NULL;
    guint watchdog_id;
    EovpnAsyncResult state = {0};

    eovpn_clear_last_error ();

    if (uuid == NULL)
    {
        eovpn_set_last_error ("Cannot disconnect a VPN connection without a UUID.");
        return false;
    }

    loop = eovpn_operation_loop_new (&context);
    client = nm_client_new (NULL, NULL);
    if (client == NULL)
    {
        eovpn_set_last_error ("Could not create a NetworkManager client.");
        eovpn_operation_loop_free (context, loop);
        return false;
    }
    arr = nm_client_get_active_connections (client);

    if (arr != NULL)
    {
        for (size_t i = 0; i < arr->len; i++)
        {
            const char *current_uuid = nm_active_connection_get_uuid (arr->pdata[i]);
            if (current_uuid != NULL && strcmp (uuid, current_uuid) == 0)
            {
                target = arr->pdata[i];
                break;
            }
        }
    }

    state.loop = loop;
    if (target != NULL)
    {
        nm_client_deactivate_connection_async (client, target, NULL,
                                               (GAsyncReadyCallback) disconnect_cb, &state);
        watchdog_id = eovpn_watchdog_attach (context, loop);
        g_main_loop_run (loop);
        eovpn_watchdog_remove (context, watchdog_id);
    }
    else
        eovpn_set_last_error ("Active VPN connection UUID was not found.");

    g_object_unref (client);
    eovpn_operation_loop_free (context, loop);
    if (!state.success && state.error != NULL)
        eovpn_set_last_error ("Failed to disconnect VPN connection: %s", state.error);
    g_free (state.error);
    return state.success;
}

static void
delete_cb (NMRemoteConnection *conn, GAsyncResult *result, EovpnAsyncResult *state)
{
    GError *err = NULL;
    nm_remote_connection_delete_finish (conn, result, &err);
    state->success = err == NULL;
    if (!state->success)
        eovpn_capture_error (state, err, "NetworkManager could not delete the VPN connection.");
    g_clear_error (&err);
    g_main_loop_quit (state->loop);
}

int
delete_connection (char *uuid)
{
    GMainContext *context;
    GMainLoop *loop;
    NMClient *client;
    const GPtrArray *arr;
    NMRemoteConnection *target = NULL;
    guint watchdog_id;
    EovpnAsyncResult state = {0};

    eovpn_clear_last_error ();

    if (uuid == NULL)
    {
        eovpn_set_last_error ("Cannot delete a VPN connection without a UUID.");
        return false;
    }

    loop = eovpn_operation_loop_new (&context);
    client = nm_client_new (NULL, NULL);
    if (client == NULL)
    {
        eovpn_set_last_error ("Could not create a NetworkManager client.");
        eovpn_operation_loop_free (context, loop);
        return false;
    }
    arr = nm_client_get_connections (client);

    if (arr != NULL)
    {
        for (size_t i = 0; i < arr->len; i++)
        {
            NMConnection *candidate = NM_CONNECTION (arr->pdata[i]);
            const char *current_uuid = nm_connection_get_uuid (candidate);
            if (eovpn_connection_is_managed (candidate) && current_uuid != NULL
                && strcmp (uuid, current_uuid) == 0)
            {
                target = NM_REMOTE_CONNECTION (candidate);
                break;
            }
        }
    }

    state.loop = loop;
    if (target != NULL)
    {
        nm_remote_connection_delete_async (target, NULL, (GAsyncReadyCallback) delete_cb, &state);
        watchdog_id = eovpn_watchdog_attach (context, loop);
        g_main_loop_run (loop);
        eovpn_watchdog_remove (context, watchdog_id);
    }
    else
        eovpn_set_last_error ("Managed VPN connection UUID was not found.");

    g_object_unref (client);
    eovpn_operation_loop_free (context, loop);
    if (!state.success && state.error != NULL)
        eovpn_set_last_error ("Failed to delete VPN connection: %s", state.error);
    g_free (state.error);
    return state.success;
}

char *
get_eovpn_active_vpn_connection_uuid (void)
{
    /* Only the duplicated UUID escapes the helper; the NMConnection object
     * itself stays owned by the (released) NMClient, so there is no use-after
     * free risk for future callers. */
    return eovpn_get_managed_active_uuid ();
}

int
delete_all_vpn_connections (void)
{
    NMClient *client;
    const GPtrArray *arr;
    GPtrArray *vpn_uuids;

    client = nm_client_new (NULL, NULL);
    arr = nm_client_get_connections (client);
    vpn_uuids = g_ptr_array_new_with_free_func (g_free);

    if (arr != NULL)
    {
        for (size_t i = 0; i < arr->len; i++)
        {
            NMConnection *conn = NM_CONNECTION (arr->pdata[i]);
            const char *uuid = nm_connection_get_uuid (conn);

            if (eovpn_connection_is_managed (conn) && uuid != NULL)
                g_ptr_array_add (vpn_uuids, g_strdup (uuid));
        }
    }

    g_object_unref (client);

    for (guint i = 0; i < vpn_uuids->len; i++)
    {
        char *u = g_ptr_array_index (vpn_uuids, i);
        g_debug ("Deleting eOVPN-managed VPN connection UUID: %s", u);
        delete_connection (u);
    }

    g_ptr_array_free (vpn_uuids, TRUE);
    return true;
}

int
is_vpn_running (void)
{
    char *uuid = get_eovpn_active_vpn_connection_uuid ();

    if (uuid != NULL)
    {
        g_free (uuid);
        return true;
    }
    return false;
}

int
is_vpn_activated (char *uuid)
{
    NMClient *client;
    const GPtrArray *arr;
    int state = -1;

    if (uuid == NULL)
        return -1;

    client = nm_client_new (NULL, NULL);
    arr = nm_client_get_active_connections (client);

    if (arr != NULL)
    {
        for (size_t i = 0; i < arr->len; i++)
        {
            NMActiveConnection *active = arr->pdata[i];
            const char *current_uuid = nm_active_connection_get_uuid (active);

            /* Only cast when the active connection really is a VPN one;
             * a plain device connection with a colliding UUID must never
             * reach nm_vpn_connection_get_vpn_state(). */
            if (current_uuid != NULL && strcmp (uuid, current_uuid) == 0
                && NM_IS_VPN_CONNECTION (active))
            {
                state = nm_vpn_connection_get_vpn_state (NM_VPN_CONNECTION (active));
                break;
            }
        }
    }

    g_object_unref (client);
    return state;
}

char *
get_version (void)
{
    GError *err = NULL;
    NMClient *client;
    const char *ver;
    char *result_ver;

    eovpn_clear_last_error ();
    client = nm_client_new (NULL, &err);
    if (err != NULL)
    {
        eovpn_set_last_error ("Error getting NetworkManager version: %s", err->message);
        g_error_free (err);
        return NULL;
    }

    ver = nm_client_get_version (client);
    result_ver = ver ? g_strdup (ver) : NULL;
    g_object_unref (client);
    return result_ver;
}

int
is_openvpn_plugin_available (void)
{
    GSList *plugins;
    bool found = false;

    plugins = nm_vpn_plugin_info_list_load ();
    if (plugins == NULL)
        return false;

    for (GSList *iter = plugins; iter != NULL; iter = iter->next)
    {
        const char *name = nm_vpn_plugin_info_get_name (iter->data);
        if (name != NULL && strcmp ("openvpn", name) == 0)
        {
            found = true;
            break;
        }
    }

    g_slist_free_full (plugins, g_object_unref);
    return found;
}
