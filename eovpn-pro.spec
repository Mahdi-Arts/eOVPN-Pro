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
BuildRequires:  libappstream-glib

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
%autosetup -n eOVPN-Pro

%build
%meson -Dopenvpn3=false
%meson_build

%install
%meson_install
%find_lang eovpn

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/com.github.mahdi-bagheban.eovpn-pro.desktop
appstream-util validate-relax --nonet %{buildroot}%{_datadir}/metainfo/com.github.mahdi-bagheban.eovpn-pro.metainfo.xml || true

%files -f eovpn.lang
%license LICENSE
%doc README.md PACKAGING.md
%{_bindir}/eovpn
%{python3_sitelib}/eovpn/
%{_datadir}/eovpn/
%{_datadir}/applications/com.github.mahdi-bagheban.eovpn-pro.desktop
%{_datadir}/metainfo/com.github.mahdi-bagheban.eovpn-pro.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/com.github.mahdi-bagheban.eovpn-pro.svg
%{_datadir}/glib-2.0/schemas/com.github.mahdi-bagheban.eovpn-pro.gschema.xml

%changelog
* Sat Aug 22 2026 Mahdi Bagheban <info@MahdiArts.ir> - 1.5.0-1
- Release version 1.5.0 with full Persian RTL localization, TCP latency test, and DCO support.
