#!/bin/bash
# Builds the .rpm and .deb packages into dist/.
#   ./paketleme/paketle.sh
# Needs: rpmbuild (Fedora: rpm-build), dpkg-deb (Fedora: dpkg)
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

SURUM="$(python3 -c 'import sys; sys.path.insert(0, "."); from drivux import ortak; print(ortak.SURUM)')"
KIMLIK="io.github.abdullahnil.Drivux"
DIST="$PWD/dist"
IS="$(mktemp -d)"
trap 'rm -rf "$IS"' EXIT
mkdir -p "$DIST"

python3 paketleme/ceviri-kontrol.py

# ---------- shared file tree ----------
K="$IS/kok"
install -d "$K/usr/bin" "$K/usr/share/drivux" "$K/usr/share/applications" \
           "$K/usr/share/icons/hicolor/scalable/apps" "$K/usr/share/icons/hicolor/symbolic/apps" \
           "$K/etc/xdg/autostart" "$K/usr/lib/systemd/user" \
           "$K/usr/share/doc/drivux" "$K/usr/share/licenses/drivux"
cp -r drivux "$K/usr/share/drivux/"
find "$K" -name __pycache__ -prune -exec rm -rf {} +
sed "s|@PYDIR@|/usr/share/drivux|" veri/drivux.sh > "$K/usr/bin/drivux"
chmod 755 "$K/usr/bin/drivux"
install -m 644 veri/drivux.desktop "$K/usr/share/applications/$KIMLIK.desktop"
install -m 644 "veri/$KIMLIK.svg" "$K/usr/share/icons/hicolor/scalable/apps/"
install -m 644 "veri/$KIMLIK-symbolic.svg" "$K/usr/share/icons/hicolor/symbolic/apps/"
install -m 644 veri/drivux-tray.desktop "$K/etc/xdg/autostart/$KIMLIK.tray.desktop"
for s in systemd/*.service; do
    sed "s|@BINDIR@|/usr/bin|g" "$s" > "$K/usr/lib/systemd/user/$(basename "$s")"
done
install -m 644 README.md README.tr.md "$K/usr/share/doc/drivux/"
install -m 644 LICENSE "$K/usr/share/licenses/drivux/"
find "$K" -type d -exec chmod 755 {} +
find "$K/usr/share" "$K/usr/lib" "$K/etc" -type f -exec chmod 644 {} +

# ---------- .rpm ----------
if command -v rpmbuild >/dev/null; then
    rpmbuild -bb paketleme/drivux.spec --quiet \
        --define "_topdir $IS/rpm" --define "surum $SURUM" --define "kaynak $K" \
        --define "dist %{nil}" --define "_rpmdir $DIST" --define "_build_name_fmt %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm"
    echo "RPM: $DIST/drivux-$SURUM-1.noarch.rpm"
else
    echo "rpmbuild not found, skipping .rpm (Fedora: sudo dnf install rpm-build)"
fi

# ---------- .deb ----------
if command -v dpkg-deb >/dev/null; then
    D="$IS/deb"
    cp -a "$K" "$D"
    rm -rf "$D/usr/share/licenses"
    install -m 644 LICENSE "$D/usr/share/doc/drivux/copyright"
    install -d "$D/DEBIAN"
    sed "s|@SURUM@|$SURUM|" paketleme/control > "$D/DEBIAN/control"
    echo "Installed-Size: $(du -sk "$D/usr" | cut -f1)" >> "$D/DEBIAN/control"
    dpkg-deb --root-owner-group -Zxz --build "$D" "$DIST/drivux_${SURUM}_all.deb" >/dev/null
    echo "DEB: $DIST/drivux_${SURUM}_all.deb"
else
    echo "dpkg-deb not found, skipping .deb (Fedora: sudo dnf install dpkg)"
fi
