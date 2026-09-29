#!/usr/bin/env bash
# Boots the built ISO in a QEMU virtual machine.  Pass --uefi to boot with UEFI firmware instead of BIOS.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
# shellcheck source=../config/os.conf
source config/os.conf

ISO="out/${OS_ID}-${OS_VERSION}-${ARCH}.iso"
[[ -f $ISO ]] || { echo "No ISO at $ISO — run 'make build' first." >&2; exit 1; }

args=(-m 4G -smp 4 -cdrom "$ISO" -boot d -vga virtio -display gtk -nic user,model=virtio-net-pci)

if [[ -w /dev/kvm ]]; then
  args+=(-enable-kvm -cpu host)
else
  echo "warning: /dev/kvm not accessible, the VM will be very slow" >&2
fi

if [[ ${1:-} == --uefi ]]; then
  args+=(-bios /usr/share/ovmf/OVMF.fd)
fi

exec qemu-system-x86_64 "${args[@]}"
