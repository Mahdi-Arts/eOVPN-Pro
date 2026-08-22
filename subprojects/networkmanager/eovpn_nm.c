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

#define NM_OPENVPN_KEY_USERNAME "username"
#define NM_OPENVPN_KEY_PASSWORD "password"
#define NM_OPENVPN_KEY_CA "ca"

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
    GMainLoop *loop = g_main_loop_new (NULL, FALSE);
    GSList *plugins = nm_vpn_plugin_info_list_load ();
    GSList *iter = NULL;
    NMVpnPluginInfo *plugin = NULL;
    GError *err = NULL;

    for (iter = plugins; iter != NULL; iter = iter->next)
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
            g_slist_free_full (plugins, g_object_unref);
            g_main_loop_unref (loop);
            return NULL;
        }

    NMVpnEditorPlugin *editor = nm_vpn_plugin_info_load_editor_plugin (plugin, &err);
    if (err != NULL)
        {
            g_printerr ("Failed to load VPN editor plugin: %s\n", err->message);
            g_error_free (err);
            g_slist_free_full (plugins, g_object_unref);
            g_main_loop_unref (loop);
            return NULL;
        }

    NMConnection *conn = nm_vpn_editor_plugin_import (editor, config_name, &err);
    if (err != NULL)
        {
            g_printerr ("Failed to import VPN config: %s\n", err->message);
            g_error_free (err);
            g_slist_free_full (plugins, g_object_unref);
            g_main_loop_unref (loop);
            return NULL;
        }

    NMSettingVpn *vpn_settings = nm_connection_get_setting_vpn (conn);
    if (vpn_settings != NULL)
        {
            if (username != NULL && strlen (username) > 0)
                {
                    nm_setting_vpn_add_data_item (vpn_settings, NM_OPENVPN_KEY_USERNAME, username);
                }
            if (password != NULL && strlen (password) > 0)
                {
                    nm_setting_vpn_add_secret (vpn_settings, NM_OPENVPN_KEY_PASSWORD, password);
                }
            if (ca != NULL && strlen (ca) > 0)
                {
                    nm_setting_vpn_add_data_item (vpn_settings, NM_OPENVPN_KEY_CA, ca);
                }
        }

    nm_connection_normalize (conn, NULL, NULL, NULL);

    NMClient *client = nm_client_new (NULL, NULL);
    nm_client_add_connection_async (client, conn, TRUE, NULL, (GAsyncReadyCallback) add_cb, loop);
    g_main_loop_run (loop);

    const char *conn_uuid = nm_connection_get_uuid (conn);
    char *result_uuid = conn_uuid ? g_strdup (conn_uuid) : NULL;

    g_slist_free_full (plugins, g_object_unref);
    g_object_unref (client);
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
    if (uuid == NULL)
        return false;

    GMainLoop *loop = g_main_loop_new (NULL, FALSE);
    NMClient *client = nm_client_new (NULL, NULL);
    const GPtrArray *arr = nm_client_get_connections (client);
    NMConnection *target = NULL;

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

    if (target != NULL)
        {
            nm_client_activate_connection_async (client, target, NULL, NULL, NULL, (GAsyncReadyCallback) activate_cb, loop);
            g_main_loop_run (loop);
        }

    g_object_unref (client);
    g_main_loop_unref (loop);
    return (target != NULL);
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
    if (uuid == NULL)
        return false;

    GMainLoop *loop = g_main_loop_new (NULL, FALSE);
    NMClient *client = nm_client_new (NULL, NULL);
    const GPtrArray *arr = nm_client_get_active_connections (client);
    NMActiveConnection *target = NULL;

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

    if (target != NULL)
        {
            nm_client_deactivate_connection_async (client, target, NULL, (GAsyncReadyCallback) disconnect_cb, loop);
            g_main_loop_run (loop);
        }

    g_object_unref (client);
    g_main_loop_unref (loop);
    return (target != NULL);
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
    if (uuid == NULL)
        return false;

    GMainLoop *loop = g_main_loop_new (NULL, FALSE);
    NMClient *client = nm_client_new (NULL, NULL);
    const GPtrArray *arr = nm_client_get_connections (client);
    NMRemoteConnection *target = NULL;

    if (arr != NULL)
        {
            for (size_t i = 0; i < arr->len; i++)
                {
                    const char *current_uuid = nm_connection_get_uuid (NM_CONNECTION (arr->pdata[i]));
                    if (current_uuid != NULL && strcmp (uuid, current_uuid) == 0)
                        {
                            target = NM_REMOTE_CONNECTION (arr->pdata[i]);
                            break;
                        }
                }
        }

    if (target != NULL)
        {
            nm_remote_connection_delete_async (target, NULL, (GAsyncReadyCallback) delete_cb, loop);
            g_main_loop_run (loop);
        }

    g_object_unref (client);
    g_main_loop_unref (loop);
    return (target != NULL);
}

char *
get_active_vpn_connection_uuid (void)
{
    NMClient *client = nm_client_new (NULL, NULL);
    const GPtrArray *arr = nm_client_get_active_connections (client);
    char *result_uuid = NULL;

    if (arr != NULL)
        {
            for (size_t i = 0; i < arr->len; i++)
                {
                    const char *conn_type = nm_active_connection_get_connection_type (arr->pdata[i]);
                    if (conn_type != NULL && strcmp (conn_type, "vpn") == 0)
                        {
                            const char *u = nm_active_connection_get_uuid (arr->pdata[i]);
                            if (u != NULL)
                                {
                                    result_uuid = g_strdup (u);
                                    break;
                                }
                        }
                }
        }

    g_object_unref (client);
    return result_uuid;
}

int
delete_all_vpn_connections (void)
{
    NMClient *client = nm_client_new (NULL, NULL);
    const GPtrArray *arr = nm_client_get_connections (client);
    GPtrArray *vpn_uuids = g_ptr_array_new_with_free_func (g_free);

    if (arr != NULL)
        {
            for (size_t i = 0; i < arr->len; i++)
                {
                    const char *uuid = nm_connection_get_uuid (arr->pdata[i]);
                    NMSetting *is_vpn = nm_connection_get_setting_by_name (arr->pdata[i], "vpn");
                    if (is_vpn != NULL && uuid != NULL)
                        {
                            g_ptr_array_add (vpn_uuids, g_strdup (uuid));
                        }
                }
        }

    g_object_unref (client);

    for (guint i = 0; i < vpn_uuids->len; i++)
        {
            char *u = g_ptr_array_index (vpn_uuids, i);
            g_debug ("Deleting VPN connection UUID: %s", u);
            delete_connection (u);
        }

    g_ptr_array_free (vpn_uuids, TRUE);
    return true;
}

int
is_vpn_running (void)
{
    NMClient *client = nm_client_new (NULL, NULL);
    const GPtrArray *arr = nm_client_get_active_connections (client);
    bool running = false;

    if (arr != NULL)
        {
            for (size_t i = 0; i < arr->len; i++)
                {
                    const char *con_type = nm_active_connection_get_connection_type (arr->pdata[i]);
                    if (con_type != NULL && strcmp ("vpn", con_type) == 0)
                        {
                            running = true;
                            break;
                        }
                }
        }

    g_object_unref (client);
    return running;
}

int
is_vpn_activated (char *uuid)
{
    if (uuid == NULL)
        return -1;

    NMClient *client = nm_client_new (NULL, NULL);
    const GPtrArray *arr = nm_client_get_active_connections (client);
    NMActiveConnection *target = NULL;

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

    if (target == NULL)
        {
            g_object_unref (client);
            return -1;
        }

    NMVpnConnectionState state = nm_vpn_connection_get_vpn_state (NM_VPN_CONNECTION (target));
    g_object_unref (client);
    return state;
}

char *
get_version (void)
{
    GError *err = NULL;
    NMClient *client = nm_client_new (NULL, &err);
    if (err != NULL)
        {
            g_printerr ("Error getting NM version: %s\n", err->message);
            g_error_free (err);
            return NULL;
        }

    const char *ver = nm_client_get_version (client);
    char *result_ver = ver ? g_strdup (ver) : NULL;
    g_object_unref (client);
    return result_ver;
}

int
is_openvpn_plugin_available (void)
{
    GSList *plugins = nm_vpn_plugin_info_list_load ();
    GSList *iter;
    bool found = false;

    if (plugins == NULL)
        return false;

    for (iter = plugins; iter; iter = iter->next)
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
