Name:           drivux
Version:        %{surum}
Release:        1%{?dist}
Summary:        Google Drive client for Linux: mount Drive as a disk and two-way sync folders
License:        MIT
URL:            https://github.com/abdullahnil/drivux
BuildArch:      noarch

Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita >= 1.5
Requires:       fuse3
Requires:       libnotify
Recommends:     rclone
Recommends:     libappindicator-gtk3
Recommends:     (gnome-shell-extension-appindicator if gnome-shell)

%description
Drivux is a GNOME-style Google Drive client built on rclone. It mounts
Google Drive as a disk in the file manager and keeps selected folders in
two-way sync. A first-run wizard installs rclone and connects the account.

%install
cp -a %{kaynak}/. %{buildroot}/

%files
%license /usr/share/licenses/drivux/LICENSE
%doc /usr/share/doc/drivux/README.md
%doc /usr/share/doc/drivux/README.tr.md
/usr/bin/drivux
/usr/share/drivux/
/usr/share/applications/io.github.abdullahnil.Drivux.desktop
/usr/share/icons/hicolor/scalable/apps/io.github.abdullahnil.Drivux.svg
/usr/share/icons/hicolor/symbolic/apps/io.github.abdullahnil.Drivux-symbolic.svg
%config(noreplace) /etc/xdg/autostart/io.github.abdullahnil.Drivux.tray.desktop
/usr/lib/systemd/user/drivux.service
/usr/lib/systemd/user/drivux-disk.service

%changelog
* Mon Nov 23 2026 abdullahnil - 1.5.0-1
- Built-in updates: checks GitHub once a day, installs the new .rpm/.deb or source release

* Mon Nov 23 2026 abdullahnil - 1.4.0-1
- Top bar (tray) icon with status and quick actions
- Faster browsing: the first folder levels are read in advance after mounting

* Mon Nov 23 2026 abdullahnil - 1.3.0-1
- New name: Drivux. English interface (Turkish follows the system language)
- Storage view shows Drive, Gmail and Google Photos usage separately
* Mon Nov 23 2026 abdullahnil - 1.2.0-1
- Yeni ad: G-Drivux; yeni uygulama simgesi; eski Drive Bağlantı kurulumundan otomatik geçiş
* Mon Nov 23 2026 abdullahnil - 1.1.0-1
- Kurulum sihirbazı, rclone'un otomatik kurulumu, Google Docs kısayolları, .rpm/.deb paketleri
