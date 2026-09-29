#!/usr/bin/env bash
# Boots Wings of Fire OS in a QEMU virtual machine.
#   run-qemu.sh               live ISO, BIOS firmware
#   run-qemu.sh --uefi        live ISO, UEFI firmware
#   run-qemu.sh --disks       also attach two blank 128 GB virtual SSDs (like the real PC) to install onto
#   run-qemu.sh --installed   boot the virtual SSDs without the ISO, to test the installed system
# Options can be combined; the UEFI boot entries persist between runs like on real hardware.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
# shellcheck source=../config/os.conf
source config/os.conf

ISO="out/${OS_ID}-${OS_VERSION}-${ARCH}.iso"
VM_DIR="build/vm"
DISK_SIZE="128G"
OVMF_CODE="/usr/share/OVMF/OVMF_CODE_4M.fd"
OVMF_VARS="/usr/share/OVMF/OVMF_VARS_4M.fd"

uefi=no disks=no installed=no
for arg in "$@"; do
  case "$arg" in
    --uefi) uefi=yes ;;
    --disks) disks=yes ;;
    --installed) installed=yes disks=yes ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

args=(-m 4G -smp 4 -vga virtio -display gtk -nic user,model=virtio-net-pci)

if [[ -w /dev/kvm ]]; then
  args+=(-enable-kvm -cpu host)
else
  echo "warning: /dev/kvm not accessible, the VM will be very slow" >&2
fi

if [[ $uefi == yes ]]; then
  mkdir -p "$VM_DIR"
  [[ -f $VM_DIR/uefi-vars.fd ]] || cp "$OVMF_VARS" "$VM_DIR/uefi-vars.fd"
  args+=(-drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE"
         -drive "if=pflash,format=raw,file=$VM_DIR/uefi-vars.fd")
fi

if [[ $disks == yes ]]; then
  mkdir -p "$VM_DIR"
  for n in 1 2; do
    disk="$VM_DIR/ssd$n.qcow2"
    [[ -f $disk ]] || qemu-img create -q -f qcow2 "$disk" "$DISK_SIZE"
    args+=(-drive "file=$disk,if=none,id=ssd$n,format=qcow2" -device "nvme,drive=ssd$n,serial=wofssd$n")
  done
fi

if [[ $installed == yes ]]; then
  if [[ ! -f $VM_DIR/ssd1.qcow2 ]]; then
    echo "No virtual SSDs yet — install first with 'make run-install'." >&2
    exit 1
  fi
else
  [[ -f $ISO ]] || { echo "No ISO at $ISO — run 'make build' first." >&2; exit 1; }
  args+=(-cdrom "$ISO" -boot once=d)
fi

exec qemu-system-x86_64 "${args[@]}"
