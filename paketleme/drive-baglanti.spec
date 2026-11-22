Name:           drive-baglanti
Version:        %{surum}
Release:        1%{?dist}
Summary:        Google Drive'ı disk olarak bağlar ve klasörleri iki yönlü eşitler
License:        MIT
URL:            https://github.com/abdullahnil/drive-baglanti
BuildArch:      noarch

Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita >= 1.5
Requires:       fuse3
Requires:       libnotify
Recommends:     rclone

%description
Drive Bağlantı, rclone üzerine kurulu GNOME tarzı bir Google Drive istemcisidir.
Drive'ı Dosyalar'da bir disk olarak bağlar ve seçilen klasörleri iki yönlü eşitler.
İlk açılışta bir sihirbaz rclone'u kurar ve Google hesabını bağlar.

%install
cp -a %{kaynak}/. %{buildroot}/

%files
%license /usr/share/licenses/drive-baglanti/LICENSE
%doc /usr/share/doc/drive-baglanti/README.md
/usr/bin/drive-baglanti
/usr/share/drive-baglanti/
/usr/share/applications/io.github.abdullahnil.DriveBaglanti.desktop
/usr/share/icons/hicolor/scalable/apps/io.github.abdullahnil.DriveBaglanti.svg
/usr/lib/systemd/user/drive-baglanti.service
/usr/lib/systemd/user/drive-baglanti-disk.service

%changelog
* Mon Nov 23 2026 abdullahnil - 1.1.0-1
- Kurulum sihirbazı, rclone'un otomatik kurulumu, Google Docs kısayolları, .rpm/.deb paketleri
