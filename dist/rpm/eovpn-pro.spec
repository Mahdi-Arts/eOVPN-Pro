Name:           eovpn-pro
Version:        1.5.0
Release:        1%{?dist}
Summary:        Advanced OpenVPN GUI Configuration Manager and Speed Tester

License:        GPL-3.0-or-later
URL:            https://github.com/Mahdi-Arts/eOVPN-Pro
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  meson >= 0.60.0
BuildRequires:  ninja-build
BuildRequires:  gcc
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(libnm)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(libadwaita-1)
BuildRequires:  pkgconfig(libsecret-1)
BuildRequires:  pkgconfig(libnotify)
BuildRequires:  python3-devel
BuildRequires:  python3-cffi
BuildRequires:  gettext
BuildRequires:  desktop-file-utils
BuildRequires:  appstream

Requires:       python3-gobject >= 3.42
Requires:       gtk4
Requires:       libadwaita
Requires:       libsecret
Requires:       libnotify
Requires:       NetworkManager-libnm
Requires:       NetworkManager-openvpn
Requires:       openvpn
Requires:       python3-cffi

%description
eOVPN-Pro is an advanced, high-performance OpenVPN configuration manager built
with GTK4 and Libadwaita. It features concurrent multi-threaded TCP latency
testing, dynamic server sorting, real-time network bandwidth monitoring,
OpenVPN 3 DCO kernel acceleration, and full Persian (RTL) localization.

%prep
%autosetup

%build
%meson -Dopenvpn3=false
%meson_build

%install
%meson_install
%find_lang eovpn

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/com.github.mahdi-arts.eovpn-pro.desktop
appstreamcli validate --no-net %{buildroot}%{_datadir}/metainfo/com.github.mahdi-arts.eovpn-pro.metainfo.xml || true

%files -f eovpn.lang
%license LICENSE
%doc README.md PACKAGING.md CHANGELOG.md
%{_bindir}/eovpn
%{_mandir}/man1/eovpn.1*
%{python3_sitelib}/eovpn/
%{_datadir}/eovpn/
%{_datadir}/applications/com.github.mahdi-arts.eovpn-pro.desktop
%{_datadir}/metainfo/com.github.mahdi-arts.eovpn-pro.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/com.github.mahdi-arts.eovpn-pro.svg
%{_datadir}/glib-2.0/schemas/com.github.mahdi-arts.eovpn-pro.gschema.xml

%changelog
* Sat Aug 22 2026 Mahdi Bagheban <info@MahdiArts.ir> - 1.5.0-1
- Release 1.5.0: Persian RTL localization, TCP latency test, DCO support.
- Added live search, smart filters and favorite servers.
- Security hardening: no OTP logging, delete-all confirmation, ZIP size caps, staging download.
- Updated application ID to com.github.mahdi-arts.eovpn-pro.
