#!/bin/sh
# Runs inside the chroot. Replaces Debian's identity with Wings of Fire OS.
set -eu

# Divert so Debian's base-files upgrades don't put its os-release back.
dpkg-divert --local --rename --add /usr/lib/os-release
cat > /usr/lib/os-release <<EOF
PRETTY_NAME="$OS_NAME $OS_VERSION ($OS_CODENAME)"
NAME="$OS_NAME"
VERSION="$OS_VERSION ($OS_CODENAME)"
VERSION_ID="$OS_VERSION"
ID=$OS_ID
ID_LIKE=debian
VERSION_CODENAME=$DEBIAN_SUITE
LOGO=wingsoffire-logo
EOF
ln -sf ../usr/lib/os-release /etc/os-release

printf '%s %s \\n \\l\n\n' "$OS_NAME" "$OS_VERSION" > /etc/issue
printf '%s %s\n' "$OS_NAME" "$OS_VERSION" > /etc/issue.net

cat > /etc/motd <<EOF

   Welcome to $OS_NAME $OS_VERSION "$OS_CODENAME"
   Built on Debian $DEBIAN_SUITE.

EOF

# The emblem (artwork/logo.png) as the login screen's picture for users without their own, and the
# boot menu background of installed systems (the live ISO's menu gets it from build.sh).
ART="/usr/share/$OS_ID/artwork"
if [ -d /etc/lightdm ]; then
  mkdir -p /etc/lightdm/lightdm-gtk-greeter.conf.d
  printf '[greeter]\ndefault-user-image=%s\n' "$ART/logo.png" \
    > /etc/lightdm/lightdm-gtk-greeter.conf.d/40-wingsoffire-logo.conf
fi
mkdir -p /etc/default/grub.d
printf 'GRUB_BACKGROUND="%s"\n' "$ART/grub.png" > /etc/default/grub.d/wingsoffire.cfg
