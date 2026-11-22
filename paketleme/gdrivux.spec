Name:           gdrivux
Version:        %{surum}
Release:        1%{?dist}
Summary:        Google Drive client for Linux: mount Drive as a disk and two-way sync folders
License:        MIT
URL:            https://github.com/abdullahnil/gdrivux
BuildArch:      noarch

Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita >= 1.5
Requires:       fuse3
Requires:       libnotify
Recommends:     rclone

%description
G-Drivux is a GNOME-style Google Drive client built on rclone. It mounts
Google Drive as a disk in the file manager and keeps selected folders in
two-way sync. A first-run wizard installs rclone and connects the account.

%install
cp -a %{kaynak}/. %{buildroot}/

%files
%license /usr/share/licenses/gdrivux/LICENSE
%doc /usr/share/doc/gdrivux/README.md
%doc /usr/share/doc/gdrivux/README.tr.md
/usr/bin/gdrivux
/usr/share/gdrivux/
/usr/share/applications/io.github.abdullahnil.GDrivux.desktop
/usr/share/icons/hicolor/scalable/apps/io.github.abdullahnil.GDrivux.svg
/usr/lib/systemd/user/gdrivux.service
/usr/lib/systemd/user/gdrivux-disk.service

%changelog
* Mon Nov 23 2026 abdullahnil - 1.2.0-1
- Yeni ad: G-Drivux; yeni uygulama simgesi; eski Drive Bağlantı kurulumundan otomatik geçiş
* Mon Nov 23 2026 abdullahnil - 1.1.0-1
- Kurulum sihirbazı, rclone'un otomatik kurulumu, Google Docs kısayolları, .rpm/.deb paketleri
