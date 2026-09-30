#!/bin/sh
# Runs inside the chroot. Generates every tribe's themes, icons, sounds and placeholder wallpapers,
# and themes the login screen with the default tribe.
set -eu

DATA="/usr/share/$OS_ID"
[ -d "$DATA/tribes" ] || exit 0

wof-tribe build-assets /usr/share --tribes-dir "$DATA/tribes"

for theme in /usr/share/icons/WoF-*; do
  gtk-update-icon-cache -q -f "$theme" || true
done
gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
fc-cache -f >/dev/null 2>&1 || true
update-desktop-database -q /usr/share/applications 2>/dev/null || true

# Every tribe's wallpapers, also browsable from XFCE's own desktop settings.
install -d "/usr/share/backgrounds/$OS_ID"
for wall in "$DATA"/tribes/*/wallpapers/*; do
  tribe=$(basename "$(dirname "$(dirname "$wall")")")
  ln -sf "$wall" "/usr/share/backgrounds/$OS_ID/$tribe-$(basename "$wall")"
done

/usr/libexec/$OS_ID/wof-login-theme "$DEFAULT_TRIBE"
