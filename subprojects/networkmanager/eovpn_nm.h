char *add_connection (char *config_path,
                      char *profile_name,
                      char *username,
                      char *password,
                      char *ca);
int activate_connection (char *uuid);
int disconnect (char *uuid);
int delete_connection (char *uuid);
char *get_active_vpn_connection_path (char *uuid);
char *get_version (void);
int is_vpn_activated (char *uuid);
int is_openvpn_plugin_available (void);
void eovpn_free (char *value);
