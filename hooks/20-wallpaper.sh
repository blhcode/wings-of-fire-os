#!/bin/sh
# Runs inside the chroot. Makes the default tribe's wallpaper the fallback desktop background (used
# before a user's first login applies their tribe, and by anything that ignores the tribe system).
set -eu

[ -f "$DEFAULT_WALLPAPER" ] || exit 0

# Debian's desktops (XFCE included) read their default background through this alternative.
if update-alternatives --list desktop-background >/dev/null 2>&1; then
  update-alternatives --install /usr/share/images/desktop-base/desktop-background \
    desktop-background "$DEFAULT_WALLPAPER" 100
  update-alternatives --set desktop-background "$DEFAULT_WALLPAPER"
fi

if [ -d /etc/lightdm ]; then
  mkdir -p /etc/lightdm/lightdm-gtk-greeter.conf.d
  printf '[greeter]\nbackground=%s\n' "$DEFAULT_WALLPAPER" \
    > /etc/lightdm/lightdm-gtk-greeter.conf.d/50-wallpaper.conf
fi
