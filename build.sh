#!/usr/bin/env bash
# Builds the Wings of Fire OS live ISO on top of Debian.
#   sudo ./build.sh              full build -> out/<id>-<version>-<arch>.iso
#   sudo ./build.sh --clean      remove build output (keeps the package download cache)
#   sudo ./build.sh --distclean  remove everything, including the cache
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
# shellcheck source=config/os.conf
source config/os.conf

WORK="$ROOT_DIR/build"
ROOTFS="$WORK/rootfs"
ISO_DIR="$WORK/iso"
CACHE="$WORK/cache"
OUT_DIR="$ROOT_DIR/out"
ISO="$OUT_DIR/${OS_ID}-${OS_VERSION}-${ARCH}.iso"
ISO_LABEL="$(printf '%s_%s' "$OS_ID" "$OS_VERSION" | tr 'a-z.-' 'A-Z__' | cut -c1-32)"

log() { printf '\n\033[1;31m==>\033[0m \033[1m%s\033[0m\n' "$*"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

in_chroot() {
  chroot "$ROOTFS" /usr/bin/env -i \
    HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin TERM="${TERM:-xterm}" \
    LC_ALL=C DEBIAN_FRONTEND=noninteractive "$@"
}

mount_rootfs() {
  mount -t proc proc "$ROOTFS/proc"
  mount -t sysfs sys "$ROOTFS/sys"
  mount --bind /dev "$ROOTFS/dev"
  mount --bind /dev/pts "$ROOTFS/dev/pts"
  mount -t tmpfs tmpfs "$ROOTFS/run"
  mount --bind "$CACHE/apt" "$ROOTFS/var/cache/apt/archives"
}

unmount_rootfs() {
  local m
  for m in var/cache/apt/archives run dev/pts dev sys proc; do
    if mountpoint -q "$ROOTFS/$m" 2>/dev/null; then
      umount -l "$ROOTFS/$m"
    fi
  done
}

# --one-file-system stops rm from ever descending into a still-mounted /dev or /proc.
remove_tree() { unmount_rootfs; rm -rf --one-file-system "$@"; }

read_packages() { sed 's/#.*//' "$@" | tr -s '[:space:]' '\n' | sed '/^$/d'; }

[[ $EUID -eq 0 ]] || die "needs root: run 'sudo ./build.sh' (or 'make build')"

case "${1:-}" in
  --clean) remove_tree "$ROOTFS" "$ISO_DIR" "$OUT_DIR"; echo "Cleaned."; exit 0 ;;
  --distclean) remove_tree "$WORK" "$OUT_DIR"; echo "Cleaned everything."; exit 0 ;;
  "") ;;
  *) die "unknown option: $1" ;;
esac

for tool in debootstrap mksquashfs grub-mkrescue xorriso mcopy; do
  command -v "$tool" >/dev/null || die "missing '$tool' — run 'make deps'"
done
[[ -f /usr/share/keyrings/debian-archive-keyring.gpg ]] || die "missing Debian keyring — run 'make deps'"
[[ -d /usr/lib/grub/i386-pc ]] || echo "warning: grub-pc-bin not installed, the ISO will only boot on UEFI" >&2

PACKAGE_LISTS=(config/packages/base.list)
if [[ $DESKTOP != none ]]; then
  [[ -f config/packages/$DESKTOP.list ]] || die "no package list for DESKTOP=$DESKTOP"
  PACKAGE_LISTS+=("config/packages/$DESKTOP.list")
fi
mapfile -t PACKAGES < <(read_packages "${PACKAGE_LISTS[@]}")

trap unmount_rootfs EXIT

log "Cleaning previous build"
remove_tree "$ROOTFS" "$ISO_DIR"
mkdir -p "$ROOTFS" "$ISO_DIR/live" "$ISO_DIR/boot/grub" \
  "$CACHE/debootstrap" "$CACHE/apt/partial" "$OUT_DIR"

log "Bootstrapping Debian $DEBIAN_SUITE ($ARCH)"
debootstrap --arch="$ARCH" --variant=minbase \
  --cache-dir="$CACHE/debootstrap" \
  --keyring=/usr/share/keyrings/debian-archive-keyring.gpg \
  --include=debian-archive-keyring,ca-certificates \
  --components=main,contrib,non-free,non-free-firmware \
  "$DEBIAN_SUITE" "$ROOTFS" "$DEBIAN_MIRROR"

log "Configuring APT sources"
rm -f "$ROOTFS/etc/apt/sources.list"
cat > "$ROOTFS/etc/apt/sources.list.d/debian.sources" <<EOF
Types: deb
URIs: $DEBIAN_MIRROR
Suites: $DEBIAN_SUITE $DEBIAN_SUITE-updates
Components: main contrib non-free non-free-firmware

Types: deb
URIs: http://security.debian.org/debian-security
Suites: $DEBIAN_SUITE-security
Components: main contrib non-free non-free-firmware
EOF

# Keep package installs from trying to start services inside the chroot.
printf '#!/bin/sh\nexit 101\n' > "$ROOTFS/usr/sbin/policy-rc.d"
chmod 755 "$ROOTFS/usr/sbin/policy-rc.d"
rm -f "$ROOTFS/etc/resolv.conf"
cp -L /etc/resolv.conf "$ROOTFS/etc/resolv.conf"

echo "$OS_HOSTNAME" > "$ROOTFS/etc/hostname"
cat > "$ROOTFS/etc/hosts" <<EOF
127.0.0.1 localhost
127.0.1.1 $OS_HOSTNAME
::1       localhost ip6-localhost ip6-loopback
EOF

mount_rootfs

log "Installing ${#PACKAGES[@]} packages"
RECOMMENDS_OPT=()
[[ $INSTALL_RECOMMENDS == yes ]] || RECOMMENDS_OPT=(--no-install-recommends)
in_chroot apt-get update
in_chroot apt-get install -y "${RECOMMENDS_OPT[@]}" "${PACKAGES[@]}"

log "Applying overlay"
cp -a --no-preserve=ownership overlay/. "$ROOTFS/"
if python3 scripts/make-wallpaper.py "$WORK/art" "$OS_NAME"; then
  install -D -m 644 "$WORK/art/wallpaper.png" "$ROOTFS/usr/share/wallpapers/$OS_ID/wallpaper.png"
  install -D -m 644 "$WORK/art/grub.png" "$ISO_DIR/boot/grub/background.png"
else
  echo "warning: could not draw wallpaper (is python3-pil installed?), continuing without it" >&2
fi

HOOK_ENV=(
  "OS_NAME=$OS_NAME" "OS_ID=$OS_ID" "OS_VERSION=$OS_VERSION" "OS_CODENAME=$OS_CODENAME"
  "OS_HOSTNAME=$OS_HOSTNAME" "DEBIAN_SUITE=$DEBIAN_SUITE"
)
for hook in hooks/*.sh; do
  [[ -e $hook ]] || continue
  log "Running hook $(basename "$hook")"
  install -m 755 "$hook" "$ROOTFS/tmp/hook.sh"
  in_chroot "${HOOK_ENV[@]}" /tmp/hook.sh
  rm -f "$ROOTFS/tmp/hook.sh"
done

log "Cleaning up the root filesystem"
umount -l "$ROOTFS/var/cache/apt/archives"
in_chroot apt-get clean
rm -rf "$ROOTFS"/var/lib/apt/lists/* "$ROOTFS"/tmp/* "$ROOTFS/var/lib/dbus/machine-id"
rm -f "$ROOTFS/usr/sbin/policy-rc.d" "$ROOTFS/etc/resolv.conf"
: > "$ROOTFS/etc/machine-id"
unmount_rootfs

log "Compressing root filesystem (this takes a few minutes)"
KERNEL="$(find "$ROOTFS/boot" -maxdepth 1 -name 'vmlinuz-*' | sort -V | tail -n1)"
[[ -n $KERNEL ]] || die "no kernel found in $ROOTFS/boot"
cp "$KERNEL" "$ISO_DIR/live/vmlinuz"
cp "$ROOTFS/boot/initrd.img-${KERNEL##*/vmlinuz-}" "$ISO_DIR/live/initrd.img"
mksquashfs "$ROOTFS" "$ISO_DIR/live/filesystem.squashfs" -noappend -comp xz -b 1M

log "Creating bootable ISO"
LIVE_ARGS="live-config.hostname=$OS_HOSTNAME live-config.username=$LIVE_USERNAME"
LIVE_ARGS+=" live-config.locales=$LOCALE live-config.timezone=$TIMEZONE"
LIVE_ARGS+=" live-config.keyboard-layouts=$KEYBOARD_LAYOUT"
sed -e "s|@OS_NAME@|$OS_NAME|g" -e "s|@OS_VERSION@|$OS_VERSION|g" -e "s|@LIVE_ARGS@|$LIVE_ARGS|g" \
  config/grub.cfg.in > "$ISO_DIR/boot/grub/grub.cfg"
grub-mkrescue -o "$ISO" "$ISO_DIR" -- -volid "$ISO_LABEL"
chown "${SUDO_UID:-0}:${SUDO_GID:-0}" "$OUT_DIR" "$ISO"

log "Done: $ISO ($(du -h "$ISO" | cut -f1))"
echo "Boot it with: make run"
