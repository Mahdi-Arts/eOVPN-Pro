// clang-format off
/*
 * eOVPN-Pro scoped NetworkManager binding.
 * بایندینگ محدودشده NetworkManager برای eOVPN-Pro.
 *
 * Every mutating function requires an explicit UUID. The library never
 * enumerates and disconnects or deletes unrelated VPN profiles.
 * همه توابع تغییردهنده به UUID صریح نیاز دارند و کتابخانه هرگز
 * پروفایل‌های VPN نامرتبط را قطع یا حذف
 * نمی‌کند.
 */
// clang-format on

#define G_LOG_DOMAIN "eovpn"
#define EOVPN_OPERATION_TIMEOUT_SECONDS 15

#include <NetworkManager.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "eovpn_nm.h"

#define NM_OPENVPN_KEY_CA "ca"
#define NM_OPENVPN_KEY_PASSWORD "password"
#define NM_OPENVPN_KEY_USERNAME "username"

typedef struct
{
    GMainLoop *loop;
    GCancellable *cancellable;
    guint timeout_id;
    gboolean success;
} AsyncOperation;

static gboolean
operation_timeout_cb (gpointer user_data)
{
    AsyncOperation *operation = user_data;
    operation->timeout_id = 0;
    g_cancellable_cancel (operation->cancellable);
    return G_SOURCE_REMOVE;
}

static void
operation_init (AsyncOperation *operation)
{
    operation->loop = g_main_loop_new (NULL, FALSE);
    operation->cancellable = g_cancellable_new ();
    operation->success = FALSE;
    operation->timeout_id = g_timeout_add_seconds (
        EOVPN_OPERATION_TIMEOUT_SECONDS, operation_timeout_cb, operation);
}

static void
operation_finish (AsyncOperation *operation)
{
    if (operation->timeout_id != 0)
        g_source_remove (operation->timeout_id);
    g_clear_object (&operation->cancellable);
    g_clear_pointer (&operation->loop, g_main_loop_unref);
}

static void
operation_complete (AsyncOperation *operation, gboolean success, GError *error)
{
    operation->success = success;
    if (error != NULL)
        {
            g_warning ("NetworkManager operation failed: %s", error->message);
            g_error_free (error);
        }
    g_main_loop_quit (operation->loop);
}

static NMClient *
new_client (void)
{
    GError *error = NULL;
    NMClient *client = nm_client_new (NULL, &error);
    if (error != NULL)
        {
            g_warning ("Could not create NetworkManager client: %s",
                       error->message);
            g_error_free (error);
        }
    return client;
}

static NMConnection *
find_connection (NMClient *client, const char *uuid)
{
    const GPtrArray *connections;

    if (client == NULL || uuid == NULL)
        return NULL;
    connections = nm_client_get_connections (client);
    if (connections == NULL)
        return NULL;

    for (guint i = 0; i < connections->len; i++)
        {
            NMConnection *connection = NM_CONNECTION (connections->pdata[i]);
            const char *current_uuid = nm_connection_get_uuid (connection);
            if (g_strcmp0 (uuid, current_uuid) == 0)
                return connection;
        }
    return NULL;
}

static NMActiveConnection *
find_active_connection (NMClient *client, const char *uuid)
{
    const GPtrArray *connections;

    if (client == NULL || uuid == NULL)
        return NULL;
    connections = nm_client_get_active_connections (client);
    if (connections == NULL)
        return NULL;

    for (guint i = 0; i < connections->len; i++)
        {
            NMActiveConnection *connection = connections->pdata[i];
            const char *current_uuid =
                nm_active_connection_get_uuid (connection);
            if (g_strcmp0 (uuid, current_uuid) == 0)
                return connection;
        }
    return NULL;
}

static void
add_cb (NMClient *client, GAsyncResult *result, gpointer user_data)
{
    AsyncOperation *operation = user_data;
    GError *error = NULL;
    NMRemoteConnection *remote =
        nm_client_add_connection_finish (client, result, &error);
    operation_complete (operation, remote != NULL, error);
    g_clear_object (&remote);
}

char *
add_connection (char *config_path,
                char *profile_name,
                char *username,
                char *password,
                char *ca)
{
    GSList *plugins = NULL;
    NMVpnPluginInfo *plugin = NULL;
    NMVpnEditorPlugin *editor = NULL;
    NMConnection *connection = NULL;
    NMClient *client = NULL;
    AsyncOperation operation;
    GError *error = NULL;
    char *result_uuid = NULL;

    if (config_path == NULL || profile_name == NULL)
        return NULL;

    plugins = nm_vpn_plugin_info_list_load ();
    for (GSList *iter = plugins; iter != NULL; iter = iter->next)
        {
            NMVpnPluginInfo *candidate = iter->data;
            if (g_strcmp0 ("openvpn",
                           nm_vpn_plugin_info_get_name (candidate)) == 0)
                {
                    plugin = candidate;
                    break;
                }
        }
    if (plugin == NULL)
        {
            g_warning ("NetworkManager OpenVPN editor plugin is unavailable");
            goto cleanup;
        }

    editor = nm_vpn_plugin_info_load_editor_plugin (plugin, &error);
    if (editor == NULL)
        {
            g_warning ("Could not load OpenVPN editor plugin: %s",
                       error != NULL ? error->message : "unknown error");
            g_clear_error (&error);
            goto cleanup;
        }

    connection = nm_vpn_editor_plugin_import (editor, config_path, &error);
    if (connection == NULL)
        {
            g_warning ("Could not import OpenVPN configuration: %s",
                       error != NULL ? error->message : "unknown error");
            g_clear_error (&error);
            goto cleanup;
        }

    NMSettingConnection *connection_setting =
        nm_connection_get_setting_connection (connection);
    if (connection_setting != NULL)
        g_object_set (G_OBJECT (connection_setting),
                      NM_SETTING_CONNECTION_ID,
                      profile_name,
                      NM_SETTING_CONNECTION_AUTOCONNECT,
                      FALSE,
                      NULL);

    NMSettingVpn *vpn_setting = nm_connection_get_setting_vpn (connection);
    if (vpn_setting != NULL)
        {
            if (username != NULL && *username != '\0')
                nm_setting_vpn_add_data_item (
                    vpn_setting, NM_OPENVPN_KEY_USERNAME, username);
            if (password != NULL && *password != '\0')
                {
                    nm_setting_vpn_add_secret (
                        vpn_setting, NM_OPENVPN_KEY_PASSWORD, password);
                    if (!nm_setting_set_secret_flags (
                            NM_SETTING (vpn_setting),
                            NM_OPENVPN_KEY_PASSWORD,
                            NM_SETTING_SECRET_FLAG_AGENT_OWNED |
                                NM_SETTING_SECRET_FLAG_NOT_SAVED,
                            &error))
                        {
                            g_warning (
                                "Could not harden password secret flags: %s",
                                error != NULL ? error->message
                                              : "unknown error");
                            g_clear_error (&error);
                            goto cleanup;
                        }
                }
            if (ca != NULL && *ca != '\0')
                nm_setting_vpn_add_data_item (
                    vpn_setting, NM_OPENVPN_KEY_CA, ca);
        }

    if (!nm_connection_normalize (connection, NULL, NULL, &error))
        {
            g_warning ("Could not normalize imported VPN profile: %s",
                       error != NULL ? error->message : "unknown error");
            g_clear_error (&error);
            goto cleanup;
        }

    client = new_client ();
    if (client == NULL)
        goto cleanup;

    operation_init (&operation);
    nm_client_add_connection_async (client,
                                    connection,
                                    TRUE,
                                    operation.cancellable,
                                    (GAsyncReadyCallback) add_cb,
                                    &operation);
    g_main_loop_run (operation.loop);
    if (operation.success)
        {
            const char *uuid = nm_connection_get_uuid (connection);
            result_uuid = uuid != NULL ? g_strdup (uuid) : NULL;
        }
    operation_finish (&operation);

cleanup:
    g_clear_object (&client);
    g_clear_object (&connection);
    g_clear_object (&editor);
    g_slist_free_full (plugins, g_object_unref);
    return result_uuid;
}

static void
activate_cb (NMClient *client, GAsyncResult *result, gpointer user_data)
{
    AsyncOperation *operation = user_data;
    GError *error = NULL;
    NMActiveConnection *active =
        nm_client_activate_connection_finish (client, result, &error);
    operation_complete (operation, active != NULL, error);
    g_clear_object (&active);
}

int
activate_connection (char *uuid)
{
    NMClient *client = new_client ();
    NMConnection *target = find_connection (client, uuid);
    AsyncOperation operation;
    gboolean success = FALSE;

    if (target == NULL)
        goto cleanup;
    operation_init (&operation);
    nm_client_activate_connection_async (client,
                                         target,
                                         NULL,
                                         NULL,
                                         operation.cancellable,
                                         (GAsyncReadyCallback) activate_cb,
                                         &operation);
    g_main_loop_run (operation.loop);
    success = operation.success;
    operation_finish (&operation);

cleanup:
    g_clear_object (&client);
    return success;
}

static void
disconnect_cb (NMClient *client, GAsyncResult *result, gpointer user_data)
{
    AsyncOperation *operation = user_data;
    GError *error = NULL;
    gboolean success =
        nm_client_deactivate_connection_finish (client, result, &error);
    operation_complete (operation, success, error);
}

int
disconnect (char *uuid)
{
    NMClient *client = new_client ();
    NMActiveConnection *target = find_active_connection (client, uuid);
    AsyncOperation operation;
    gboolean success = FALSE;

    if (target == NULL)
        goto cleanup;
    operation_init (&operation);
    nm_client_deactivate_connection_async (client,
                                           target,
                                           operation.cancellable,
                                           (GAsyncReadyCallback) disconnect_cb,
                                           &operation);
    g_main_loop_run (operation.loop);
    success = operation.success;
    operation_finish (&operation);

cleanup:
    g_clear_object (&client);
    return success;
}

static void
delete_cb (NMRemoteConnection *connection,
           GAsyncResult *result,
           gpointer user_data)
{
    AsyncOperation *operation = user_data;
    GError *error = NULL;
    gboolean success =
        nm_remote_connection_delete_finish (connection, result, &error);
    operation_complete (operation, success, error);
}

int
delete_connection (char *uuid)
{
    NMClient *client = new_client ();
    NMConnection *connection = find_connection (client, uuid);
    AsyncOperation operation;
    gboolean success = FALSE;

    if (connection == NULL || !NM_IS_REMOTE_CONNECTION (connection))
        goto cleanup;
    operation_init (&operation);
    nm_remote_connection_delete_async (NM_REMOTE_CONNECTION (connection),
                                       operation.cancellable,
                                       (GAsyncReadyCallback) delete_cb,
                                       &operation);
    g_main_loop_run (operation.loop);
    success = operation.success;
    operation_finish (&operation);

cleanup:
    g_clear_object (&client);
    return success;
}

char *
get_active_vpn_connection_path (char *uuid)
{
    NMClient *client = new_client ();
    NMActiveConnection *active = find_active_connection (client, uuid);
    char *result = NULL;

    if (active != NULL)
        {
            const char *path = nm_object_get_path (NM_OBJECT (active));
            result = path != NULL ? g_strdup (path) : NULL;
        }
    g_clear_object (&client);
    return result;
}

int
is_vpn_activated (char *uuid)
{
    NMClient *client = new_client ();
    NMActiveConnection *active = find_active_connection (client, uuid);
    int state = -1;

    if (active != NULL && NM_IS_VPN_CONNECTION (active))
        state =
            (int) nm_vpn_connection_get_vpn_state (NM_VPN_CONNECTION (active));
    g_clear_object (&client);
    return state;
}

char *
get_version (void)
{
    NMClient *client = new_client ();
    char *version = NULL;

    if (client != NULL)
        {
            const char *value = nm_client_get_version (client);
            version = value != NULL ? g_strdup (value) : NULL;
        }
    g_clear_object (&client);
    return version;
}

int
is_openvpn_plugin_available (void)
{
    GSList *plugins = nm_vpn_plugin_info_list_load ();
    gboolean found = FALSE;

    for (GSList *iter = plugins; iter != NULL; iter = iter->next)
        {
            if (g_strcmp0 ("openvpn",
                           nm_vpn_plugin_info_get_name (iter->data)) == 0)
                {
                    found = TRUE;
                    break;
                }
        }
    g_slist_free_full (plugins, g_object_unref);
    return found;
}

void
eovpn_free (char *value)
{
    g_free (value);
}
