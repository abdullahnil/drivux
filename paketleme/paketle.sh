#!/bin/bash
# .rpm ve .deb paketlerini dist/ klasörüne üretir.
#   ./paketleme/paketle.sh
# Gerekenler: rpmbuild (Fedora: rpm-build), dpkg-deb (Fedora: dpkg)
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

SURUM="$(python3 -c 'import sys; sys.path.insert(0, "."); from drive_baglanti import ortak; print(ortak.SURUM)')"
KIMLIK="io.github.abdullahnil.DriveBaglanti"
DIST="$PWD/dist"
IS="$(mktemp -d)"
trap 'rm -rf "$IS"' EXIT
mkdir -p "$DIST"

# ---------- ortak dosya ağacı ----------
K="$IS/kok"
install -d "$K/usr/bin" "$K/usr/share/drive-baglanti" "$K/usr/share/applications" \
           "$K/usr/share/icons/hicolor/scalable/apps" "$K/usr/lib/systemd/user" \
           "$K/usr/share/doc/drive-baglanti" "$K/usr/share/licenses/drive-baglanti"
cp -r drive_baglanti "$K/usr/share/drive-baglanti/"
find "$K" -name __pycache__ -prune -exec rm -rf {} +
sed "s|@PYDIR@|/usr/share/drive-baglanti|" veri/drive-baglanti.sh > "$K/usr/bin/drive-baglanti"
chmod 755 "$K/usr/bin/drive-baglanti"
install -m 644 veri/drive-baglanti.desktop "$K/usr/share/applications/$KIMLIK.desktop"
install -m 644 "veri/$KIMLIK.svg" "$K/usr/share/icons/hicolor/scalable/apps/"
for s in systemd/*.service; do
    sed "s|@BINDIR@|/usr/bin|g" "$s" > "$K/usr/lib/systemd/user/$(basename "$s")"
done
install -m 644 README.md "$K/usr/share/doc/drive-baglanti/"
install -m 644 LICENSE "$K/usr/share/licenses/drive-baglanti/"
find "$K" -type d -exec chmod 755 {} +
find "$K/usr/share" "$K/usr/lib" -type f -exec chmod 644 {} +

# ---------- .rpm ----------
if command -v rpmbuild >/dev/null; then
    rpmbuild -bb paketleme/drive-baglanti.spec --quiet \
        --define "_topdir $IS/rpm" --define "surum $SURUM" --define "kaynak $K" \
        --define "dist %{nil}" --define "_rpmdir $DIST" --define "_build_name_fmt %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm"
    echo "RPM: $DIST/drive-baglanti-$SURUM-1.noarch.rpm"
else
    echo "rpmbuild yok, .rpm atlandı (Fedora: sudo dnf install rpm-build)"
fi

# ---------- .deb ----------
if command -v dpkg-deb >/dev/null; then
    D="$IS/deb"
    cp -a "$K" "$D"
    rm -rf "$D/usr/share/licenses"
    install -m 644 LICENSE "$D/usr/share/doc/drive-baglanti/copyright"
    install -d "$D/DEBIAN"
    sed "s|@SURUM@|$SURUM|" paketleme/control > "$D/DEBIAN/control"
    echo "Installed-Size: $(du -sk "$D/usr" | cut -f1)" >> "$D/DEBIAN/control"
    dpkg-deb --root-owner-group -Zxz --build "$D" "$DIST/drive-baglanti_${SURUM}_all.deb" >/dev/null
    echo "DEB: $DIST/drive-baglanti_${SURUM}_all.deb"
else
    echo "dpkg-deb yok, .deb atlandı (Fedora: sudo dnf install dpkg)"
fi
