#!/bin/sh
# Runs inside the chroot. Makes the Wings of Fire emblem the boot loading screen (Plymouth).
set -eu
command -v plymouth-set-default-theme >/dev/null || exit 0

plymouth-set-default-theme wingsoffire
update-initramfs -u -k all

if [ -d /etc/calamares/modules ]; then
  echo 'plymouth_theme: wingsoffire' > /etc/calamares/modules/plymouthcfg.conf
fi
