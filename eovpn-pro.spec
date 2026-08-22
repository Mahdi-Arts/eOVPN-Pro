Name:           eovpn-pro
Version:        1.5.0
Release:        1%{?dist}
Summary:        Secure OpenVPN profile manager for GTK4 desktops

License:        GPL-3.0-or-later
URL:            https://github.com/Mahdi-Arts/eOVPN-Pro
Source0:        %{name}-%{version}.tar.xz

BuildRequires:  meson >= 0.60.0
BuildRequires:  ninja-build
BuildRequires:  gcc
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(libnm) >= 1.30
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gtk4) >= 4.6
BuildRequires:  pkgconfig(libadwaita-1) >= 1.1
BuildRequires:  pkgconfig(libsecret-1) >= 0.20
BuildRequires:  pkgconfig(libnotify)
BuildRequires:  python3-devel >= 3.10
BuildRequires:  python3-cffi
BuildRequires:  gettext
BuildRequires:  desktop-file-utils
BuildRequires:  appstream

Requires:       python3 >= 3.10
Requires:       python3-gobject >= 3.42
Requires:       gtk4 >= 4.6
Requires:       libadwaita >= 1.1
Requires:       libsecret
Requires:       libnotify
Requires:       NetworkManager-libnm >= 1.30
Requires:       NetworkManager-openvpn
Requires:       NetworkManager-openvpn-gnome
Requires:       openvpn
Requires:       python3-cffi

%description
eOVPN-Pro imports OpenVPN profiles from private local storage or HTTPS,
performs TCP latency measurements, filters and favorites servers, and manages
only the NetworkManager UUIDs created by the application. It includes Persian
localization, RTL layout, transactional imports, and opt-in public IP lookup.

%prep
%autosetup

%build
%meson -Dopenvpn3=false
%meson_build

%install
%meson_install
%find_lang eovpn

%check
%meson_test
desktop-file-validate \
  %{buildroot}%{_datadir}/applications/io.github.Mahdi_Arts.eOVPN_Pro.desktop
appstreamcli validate --no-net \
  %{buildroot}%{_datadir}/metainfo/io.github.Mahdi_Arts.eOVPN_Pro.metainfo.xml

%files -f eovpn.lang
%license LICENSE
%doc README.md PACKAGING.md SECURITY.md CHANGELOG.md
%{_bindir}/eovpn
%{python3_sitearch}/eovpn/
%{_datadir}/eovpn/
%{_datadir}/applications/io.github.Mahdi_Arts.eOVPN_Pro.desktop
%{_datadir}/metainfo/io.github.Mahdi_Arts.eOVPN_Pro.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.Mahdi_Arts.eOVPN_Pro.svg
%{_datadir}/glib-2.0/schemas/io.github.Mahdi_Arts.eOVPN_Pro.gschema.xml
%{_datadir}/glib-2.0/schemas/com.github.mahdi-arts.eovpn-pro.gschema.xml
%{_datadir}/glib-2.0/schemas/com.github.jkotra.eovpn.gschema.xml

%changelog
* Sat Aug 22 2026 Mahdi Bagheban <info@MahdiArts.ir> - 1.5.0-1
- Scope VPN operations to application-owned UUIDs and object paths.
- Add private transactional imports, explicit credential persistence, and
  opt-in privacy controls.
- Add reproducible QA, Debian, and Flatpak release automation.
