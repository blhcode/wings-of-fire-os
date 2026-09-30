# Wings of Fire OS

A fan-made OS themed around Tui T. Sutherland's *Wings of Fire* book series. Not affiliated
with the author or Scholastic.

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

## Tribes

Every user picks a dragon tribe in **Pyrrhia Settings** (Settings menu, or `pyrrhia-settings`).
The tribe sets the wallpaper, window/panel/notification colours, file and folder icons (text files
are scrolls), terminal colours, Firefox's toolbar and new tab page, the Scroll editor's wax seal and
Mousepad's colours, system sounds and the login screen. Each part can be switched off. The same is
available from a terminal: `wof-tribe list`, `wof-tribe apply nightwing`, `wof-tribe set firefox off`.

A tribe is a folder in `desktop/tribes/<id>/`: a `tribe.toml` (name, colours, pattern, sounds, seal
colour) and a `wallpapers/` folder. Adding a folder adds a tribe; the themes, icons and sounds are
generated from `tribe.toml` when the ISO is built. Tribes without a wallpaper get a patterned
placeholder until one is added. Users can add their own wallpapers (or whole tribes) under
`~/.local/share/wingsoffire/tribes/<id>/`, which the settings app's **Add wallpapers…** does for them.

Firefox theming only touches files it owns (`chrome/wof-tribe*.css`, one `@import` line, one marked
block in `user.js`), keeps everything else, and is removed completely when switched off.

**Scroll** (`wof-scroll`) is the default text editor: a full editor (open/save, undo/redo,
search and replace, syntax highlighting, line numbers, zoom) drawn as a parchment scroll that
unrolls when it opens and rolls up when it closes. The wax seal in its toolbar cracks when there are
unsaved changes and is stamped again on save. Animations and the seal can be turned off in its
settings.

Try the apps on this PC without building (uses a throwaway home in `build/try-home`):

```sh
make try-scroll
make try-settings
make preview      # build/preview/tribes.png: every tribe's icons, wallpaper and terminal colours
make test
```

## Layout

| Path | Purpose |
| --- | --- |
| `config/os.conf` | Name, version, Debian release, desktop, default tribe, locale |
| `desktop/tribes/` | One folder per tribe: `tribe.toml` + `wallpapers/` |
| `desktop/lib/pyrrhia/` | Tribe engine: loading, theme/icon/sound generators, components, `wof-tribe` CLI, Pyrrhia Settings |
| `desktop/lib/wofscroll/` | The Scroll text editor |
| `desktop/bin`, `applications`, `autostart`, `libexec`, `polkit` | Launchers, menu entries, login-time theming, the login screen helper and its permission |
| `tests/` | Unit tests (`make test`) |
| `artwork/bootlogo.png` | Emblem on the boot loading screen (Plymouth theme in `overlay/usr/share/plymouth/themes/wingsoffire/`) |
| `artwork/fonts/WingsOfFireTitle.otf` | The book logo's lettering, traced into a font (glyphs W I N G S O F R E, small "of"), used for the "Wings of Fire OS" wordmark |
| `scripts/trace-font.py` | Rebuilds that font from the logo image (one-off; instructions inside) |
| `config/packages/*.list` | Packages installed into the image (`base.list` + the chosen desktop + installer) |
| `config/installer-pool.list` | Bootloader packages shipped on the ISO for offline installs |
| `config/grub.cfg.in` | Boot menu of the ISO |
| `overlay/` | Files copied verbatim into the root filesystem |
| `hooks/*.sh` | Scripts run inside the image after packages are installed, in order |
| `scripts/make-artwork.py` | Draws the wordmark, loading ring, logo, boot menu background and installer artwork |
| `scripts/run-qemu.sh` | Runs the ISO / installed system in QEMU |
| `build.sh` | The build pipeline |

## How the build works

1. `debootstrap` creates a minimal Debian root filesystem in `build/rootfs`.
2. Packages from `config/packages/` are installed inside it with `apt`.
3. The installer's bootloader packages are downloaded into an APT repository on the ISO (`pool/`, `dists/`).
4. `overlay/` and `desktop/` are copied in and `hooks/` are run (branding, tribe assets, wallpaper,
   installer branding, boot splash).
5. The root filesystem is compressed into `live/filesystem.squashfs`.
6. `grub-mkrescue` produces a hybrid ISO that boots on BIOS and UEFI, from a DVD or USB stick.

Downloaded packages are cached in `build/cache`, so rebuilds are much faster.
`make clean` keeps that cache; `make distclean` removes it.

## Putting it on a USB stick

```sh
sudo dd if=out/wingsoffire-0.1-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

Replace `/dev/sdX` with the USB device (check with `lsblk`); everything on it is erased.
