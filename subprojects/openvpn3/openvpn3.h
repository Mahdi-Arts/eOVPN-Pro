/*
 * eOVPN-Pro OpenVPN 3 Linux Native C / D-Bus Binding (Header)
 * فایل هدر بایندینگ بومی C جهت تعامل با D-Bus و سرویس OpenVPN 3 Linux
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

#ifndef EOVPN_OPENVPN3_H
#define EOVPN_OPENVPN3_H

int    get_connection_status (void);
void   disconnect_all_sessions (void);
int    get_specific_connection_status (char *session_path);
char  *get_version (void);
char  *import_config (char *name, char *config_str);
char  *prepare_tunnel (char *config_object);
void   set_dco (char *session_object, int set_to);
void   set_receive_log_events (char *session_object, int set_to);
void   set_log_forward (char *session_object);
char  *is_ready_to_connect (char *session_object);
void   send_auth (char *session_object, int type, int group, int id, char *value);
void   connect_vpn (char *session_object);
void   disconnect_vpn (char *session_object);
void   pause_vpn (char *session_object, char *reason);
void   resume_vpn (char *session_object);
char  *p_get_version (void);
int    p_get_connection_status (void);

#endif /* EOVPN_OPENVPN3_H */