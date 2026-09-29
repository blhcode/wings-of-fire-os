# Wings of Fire OS

A Debian-based Linux distribution with its own branding, package selection and live ISO.
It uses Debian's kernel and packages, and builds the system image itself with `debootstrap`
(no live-build or remastering of an existing ISO).

## Quick start

```sh
make deps    # one-time: install build tools on the host (asks for your sudo password)
make build   # builds out/wingsoffire-0.1-amd64.iso (first build ~15-30 min, mostly downloads)
make run     # boot the ISO in QEMU (BIOS); `make run-uefi` for UEFI
```

The live session logs in automatically as `dragon` (password `live`).

## Installing

The live desktop has an **Install Wings of Fire OS** icon (the Calamares installer). It works
offline: the bootloader packages it needs are on the ISO. It asks for confirmation before
touching any disk.

Rehearse in a VM first. This mimics the real PC: UEFI firmware and two blank 128 GB SSDs.

```sh
make run-install     # boot the ISO with the virtual SSDs, run the installer
make run-installed   # boot the installed system without the ISO
make reset-vm        # wipe the virtual SSDs to start over
```

On real hardware, check the disk picked on the installer's partitioning page: the existing
Ubuntu drive is the 1.8 TB NVMe, the new SSDs are the ~128 GB ones.

## Layout

| Path | Purpose |
| --- | --- |
| `config/os.conf` | Name, version, Debian release, desktop, default wallpaper, locale |
| `artwork/wallpapers/` | Wallpapers shipped in `/usr/share/backgrounds/wingsoffire/` |
| `config/packages/*.list` | Packages installed into the image (`base.list` + the chosen desktop + installer) |
| `config/installer-pool.list` | Bootloader packages shipped on the ISO for offline installs |
| `config/grub.cfg.in` | Boot menu of the ISO |
| `overlay/` | Files copied verbatim into the root filesystem |
| `hooks/*.sh` | Scripts run inside the image after packages are installed, in order |
| `scripts/make-artwork.py` | Draws the logo, boot menu background and installer artwork |
| `scripts/run-qemu.sh` | Runs the ISO / installed system in QEMU |
| `build.sh` | The build pipeline |

## How the build works

1. `debootstrap` creates a minimal Debian root filesystem in `build/rootfs`.
2. Packages from `config/packages/` are installed inside it with `apt`.
3. The installer's bootloader packages are downloaded into an APT repository on the ISO (`pool/`, `dists/`).
4. `overlay/` is copied in and `hooks/` are run (branding, wallpaper, installer branding).
5. The root filesystem is compressed into `live/filesystem.squashfs`.
6. `grub-mkrescue` produces a hybrid ISO that boots on BIOS and UEFI, from a DVD or USB stick.

Downloaded packages are cached in `build/cache`, so rebuilds are much faster.
`make clean` keeps that cache; `make distclean` removes it.

## Putting it on a USB stick

```sh
sudo dd if=out/wingsoffire-0.1-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

Replace `/dev/sdX` with the USB device (check with `lsblk`); everything on it is erased.
