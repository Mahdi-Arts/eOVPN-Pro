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

static gboolean
eovpn_nm_watchdog (gpointer user_data)
{
    g_warning ("[eOVPN] NetworkManager operation timed out after %d ms.",
               EOVPN_NM_TIMEOUT_MS);
    g_main_loop_quit ((GMainLoop *) user_data);
    return G_SOURCE_REMOVE;
}

static gboolean
eovpn_connection_is_managed (NMConnection *conn)
{
    NMSettingVpn *vpn;
    const char *managed;

    if (conn == NULL)
        return false;

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
    NMClient *client;
    const GPtrArray *arr;
    char *uuid = NULL;

    client = nm_client_new (NULL, NULL);
    if (client == NULL)
        return NULL;

    arr = nm_client_get_active_connections (client);
    if (arr != NULL)
    {
        for (size_t i = 0; i < arr->len; i++)
        {
            NMActiveConnection *active = arr->pdata[i];
            NMConnection *conn = nm_active_connection_get_connection (active);

            if (eovpn_connection_is_managed (conn))
            {
                const char *conn_uuid = nm_connection_get_uuid (conn);
                uuid = conn_uuid ? g_strdup (conn_uuid) : NULL;
                break;
            }
        }
    }

    g_object_unref (client);
    return uuid;
}

static void
add_cb (NMClient *client, GAsyncResult *result, GMainLoop *loop)
{
    GError *err = NULL;
    nm_client_add_connection_finish (client, result, &err);
    if (err != NULL)
    {
        g_printerr ("Error adding connection: %s\n", err->message);
        g_error_free (err);
    }
    else
    {
        g_debug ("[NM] Connection Added Successfully!");
    }

    g_main_loop_quit (loop);
}

char *
add_connection (char *config_name, char *username, char *password, char *ca)
{
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
    char *result_uuid = NULL;
    gboolean secret_flags_ok = true;

    loop = g_main_loop_new (NULL, FALSE);
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
        g_printerr ("NetworkManager OpenVPN plugin not found on system.\n");
        goto cleanup;
    }

    editor = nm_vpn_plugin_info_load_editor_plugin (plugin, &err);
    if (err != NULL)
    {
        g_printerr ("Failed to load VPN editor plugin: %s\n", err->message);
        g_clear_error (&err);
        goto cleanup;
    }

    conn = nm_vpn_editor_plugin_import (editor, config_name, &err);
    if (err != NULL)
    {
        g_printerr ("Failed to import VPN config: %s\n", err->message);
        g_clear_error (&err);
        goto cleanup;
    }

    vpn_settings = nm_connection_get_setting_vpn (conn);
    if (vpn_settings != NULL)
    {
        nm_setting_vpn_add_data_item (vpn_settings, EOVPN_MANAGED_KEY, EOVPN_MANAGED_VALUE);

        if (username != NULL && strlen (username) > 0)
            nm_setting_vpn_add_data_item (vpn_settings, NM_OPENVPN_KEY_USERNAME, username);

        if (password != NULL && strlen (password) > 0)
        {
            nm_setting_vpn_add_secret (vpn_settings, NM_OPENVPN_KEY_PASSWORD, password);

            /* Keep the password agent-owned; abort if NetworkManager cannot
             * guarantee that it will not persist the secret on disk. */
            if (!nm_setting_set_secret_flags (vpn_settings,
                                              NM_SETTING_VPN_SECRET_PASSWORD,
                                              NM_SETTING_SECRET_FLAG_AGENT_OWNED,
                                              &flags_err))
            {
                g_printerr ("Refusing to add VPN profile: failed to set agent-owned "
                            "secret flags: %s\n",
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

    nm_connection_normalize (conn, NULL, NULL, NULL);

    client = nm_client_new (NULL, NULL);
    nm_client_add_connection_async (client, conn, TRUE, NULL, (GAsyncReadyCallback) add_cb, loop);
    watchdog_id = g_timeout_add (EOVPN_NM_TIMEOUT_MS, eovpn_nm_watchdog, loop);
    g_main_loop_run (loop);
    g_source_remove (watchdog_id);

    const char *conn_uuid = nm_connection_get_uuid (conn);
    result_uuid = conn_uuid ? g_strdup (conn_uuid) : NULL;

cleanup:
    g_clear_object (&editor);
    if (plugins != NULL)
        g_slist_free_full (plugins, g_object_unref);
    g_clear_object (&client);
    if (loop != NULL)
        g_main_loop_unref (loop);

    return result_uuid;
}

static void
activate_cb (NMClient *client, GAsyncResult *result, GMainLoop *loop)
{
    GError *err = NULL;
    nm_client_activate_connection_finish (client, result, &err);
    if (err != NULL)
    {
        g_printerr ("Error activating connection: %s\n", err->message);
        g_error_free (err);
    }
    else
    {
        g_debug ("[NM] Connection Connected!");
    }

    g_main_loop_quit (loop);
}

int
activate_connection (char *uuid)
{
    GMainLoop *loop;
    NMClient *client;
    const GPtrArray *arr;
    NMConnection *target = NULL;
    guint watchdog_id;
    gboolean success;

    if (uuid == NULL)
        return false;

    loop = g_main_loop_new (NULL, FALSE);
    client = nm_client_new (NULL, NULL);
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

    success = target != NULL;
    if (target != NULL)
    {
        nm_client_activate_connection_async (client, target, NULL, NULL, NULL,
                                             (GAsyncReadyCallback) activate_cb, loop);
        watchdog_id = g_timeout_add (EOVPN_NM_TIMEOUT_MS, eovpn_nm_watchdog, loop);
        g_main_loop_run (loop);
        g_source_remove (watchdog_id);
    }

    g_object_unref (client);
    g_main_loop_unref (loop);
    return success;
}

static void
disconnect_cb (NMClient *client, GAsyncResult *result, GMainLoop *loop)
{
    GError *err = NULL;
    nm_client_deactivate_connection_finish (client, result, &err);
    if (err != NULL)
    {
        g_printerr ("Error deactivating connection: %s\n", err->message);
        g_error_free (err);
    }
    else
    {
        g_debug ("[NM] Connection Disconnected!");
    }
    g_main_loop_quit (loop);
}

int
disconnect (char *uuid)
{
    GMainLoop *loop;
    NMClient *client;
    const GPtrArray *arr;
    NMActiveConnection *target = NULL;
    guint watchdog_id;
    gboolean success;

    if (uuid == NULL)
        return false;

    loop = g_main_loop_new (NULL, FALSE);
    client = nm_client_new (NULL, NULL);
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

    success = target != NULL;
    if (target != NULL)
    {
        nm_client_deactivate_connection_async (client, target, NULL,
                                               (GAsyncReadyCallback) disconnect_cb, loop);
        watchdog_id = g_timeout_add (EOVPN_NM_TIMEOUT_MS, eovpn_nm_watchdog, loop);
        g_main_loop_run (loop);
        g_source_remove (watchdog_id);
    }

    g_object_unref (client);
    g_main_loop_unref (loop);
    return success;
}

static void
delete_cb (NMRemoteConnection *conn, GAsyncResult *result, GMainLoop *loop)
{
    GError *err = NULL;
    nm_remote_connection_delete_finish (conn, result, &err);
    if (err != NULL)
    {
        g_printerr ("Error deleting connection: %s\n", err->message);
        g_error_free (err);
    }
    else
    {
        g_debug ("[NM] Connection Deleted!");
    }
    g_main_loop_quit (loop);
}

int
delete_connection (char *uuid)
{
    GMainLoop *loop;
    NMClient *client;
    const GPtrArray *arr;
    NMRemoteConnection *target = NULL;
    guint watchdog_id;
    gboolean success;

    if (uuid == NULL)
        return false;

    loop = g_main_loop_new (NULL, FALSE);
    client = nm_client_new (NULL, NULL);
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

    success = target != NULL;
    if (target != NULL)
    {
        nm_remote_connection_delete_async (target, NULL, (GAsyncReadyCallback) delete_cb, loop);
        watchdog_id = g_timeout_add (EOVPN_NM_TIMEOUT_MS, eovpn_nm_watchdog, loop);
        g_main_loop_run (loop);
        g_source_remove (watchdog_id);
    }

    g_object_unref (client);
    g_main_loop_unref (loop);
    return success;
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

    client = nm_client_new (NULL, &err);
    if (err != NULL)
    {
        g_printerr ("Error getting NM version: %s\n", err->message);
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
