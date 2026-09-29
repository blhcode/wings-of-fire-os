#!/bin/sh
# Runs inside the chroot. Makes our wallpaper the default desktop background.
set -eu

WALLPAPER="/usr/share/backgrounds/$OS_ID/$DEFAULT_WALLPAPER"
[ -f "$WALLPAPER" ] || exit 0

# Debian's desktops (XFCE included) read their default background through this alternative.
if update-alternatives --list desktop-background >/dev/null 2>&1; then
  update-alternatives --install /usr/share/images/desktop-base/desktop-background \
    desktop-background "$WALLPAPER" 100
  update-alternatives --set desktop-background "$WALLPAPER"
fi

if [ -d /etc/lightdm ]; then
  mkdir -p /etc/lightdm/lightdm-gtk-greeter.conf.d
  printf '[greeter]\nbackground=%s\n' "$WALLPAPER" \
    > /etc/lightdm/lightdm-gtk-greeter.conf.d/50-wallpaper.conf
fi
