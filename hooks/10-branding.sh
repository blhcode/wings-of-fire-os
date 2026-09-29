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
EOF
ln -sf ../usr/lib/os-release /etc/os-release

printf '%s %s \\n \\l\n\n' "$OS_NAME" "$OS_VERSION" > /etc/issue
printf '%s %s\n' "$OS_NAME" "$OS_VERSION" > /etc/issue.net

cat > /etc/motd <<EOF

   Welcome to $OS_NAME $OS_VERSION "$OS_CODENAME"
   Built on Debian $DEBIAN_SUITE.

EOF
