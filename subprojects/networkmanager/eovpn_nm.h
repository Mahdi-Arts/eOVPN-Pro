/*
 * eOVPN-Pro NetworkManager Native C Binding (Header)
 * فایل هدر بایندینگ بومی NetworkManager در eOVPN-Pro
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

#ifndef EOVPN_NM_H
#define EOVPN_NM_H

char *add_connection (char *config_name, char *username, char *password, char *ca);
int   activate_connection (char *uuid);
int   disconnect (char *uuid);
int   delete_connection (char *uuid);
char *get_eovpn_active_vpn_connection_uuid (void);
char *get_version (void);
int   delete_all_vpn_connections (void);
int   is_vpn_running (void);
int   is_vpn_activated (char *uuid);
int   is_openvpn_plugin_available (void);

#endif /* EOVPN_NM_H */
