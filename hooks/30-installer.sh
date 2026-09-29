#!/bin/sh
# Runs inside the chroot. Rebrands Debian's Calamares installer setup and adapts it to this ISO.
set -eu
[ -d /etc/calamares ] || exit 0

ART="/usr/share/$OS_ID/artwork"
BRANDING="/etc/calamares/branding/$OS_ID"
DESC="$BRANDING/branding.desc"

cp -a /etc/calamares/branding/debian "$BRANDING"
set_key() { sed -i "s|^\( *$1: *\).*|\1$2|" "$DESC"; }
set_key componentName "$OS_ID"
set_key productName "$OS_NAME"
set_key shortProductName "$OS_NAME"
set_key version "$OS_VERSION"
set_key shortVersion "$OS_VERSION"
set_key versionedName "$OS_NAME $OS_VERSION"
set_key shortVersionedName "$OS_NAME $OS_VERSION"
set_key bootloaderEntryName "$OS_NAME"
set_key SidebarBackground '"#2a0a0a"'
set_key SidebarBackgroundCurrent '"#8c1c10"'
sed -i 's|debian-logo.png|logo.png|' "$DESC"
rm -f "$BRANDING/debian-logo.png"
if [ -d "$ART" ]; then
  cp "$ART/logo.png" "$BRANDING/logo.png"
  cp "$ART/welcome.png" "$BRANDING/welcome.png"
  cp "$ART/slide.png" "$BRANDING/slide1.png"
  cp "$ART/logo.png" /usr/share/pixmaps/install-debian.png
fi
sed -i "s|Welcome to Debian GNU/Linux.|Welcome to $OS_NAME.|" "$BRANDING/show.qml"

sed -i -e "s|^branding: .*|branding: $OS_ID|" -e "s|^prompt-install: .*|prompt-install: true|" \
  /etc/calamares/settings.conf
sed -i 's|^\(show[A-Za-z]*Url: *\)true|\1false|' /etc/calamares/modules/welcome.conf

# Debian's signed GRUB (used with Secure Boot) only finds its config under EFI/debian.
echo 'efiBootloaderId: "debian"' >> /etc/calamares/modules/bootloader.conf

sed -i "s|^\( *\)- 'calamares-settings-debian'|&\n\1- 'calamares'|" /etc/calamares/modules/packages.conf

sed -i "s|^RELEASE=.*|RELEASE=\"$DEBIAN_SUITE\"|" /usr/share/calamares/helpers/calamares-sources-media
cat > /usr/share/calamares/helpers/calamares-sources-final <<'EOF'
#!/bin/sh
# The installed system keeps /etc/apt/sources.list.d/debian.sources from the live image.
CHROOT=$(mount | grep proc | grep calamares | awk '{print $3}' | sed -e "s#/proc##g")
rm -f "$CHROOT/etc/apt/sources.list"
exit 0
EOF

sed -i "s|Install Debian|Install $OS_NAME|; s|Installer for Debian Live|Installer for $OS_NAME|" \
  /usr/share/applications/calamares-install-debian.desktop /usr/bin/add-calamares-desktop-icon
