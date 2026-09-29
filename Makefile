.PHONY: deps build run run-uefi run-install run-installed reset-vm artwork clean distclean

HOST_PACKAGES = debootstrap debian-archive-keyring squashfs-tools xorriso apt-utils \
	grub-pc-bin grub-efi-amd64-bin mtools qemu-system-x86 qemu-utils ovmf python3-pil

deps:
	sudo apt-get install -y $(HOST_PACKAGES)

build:
	sudo ./build.sh

# Try the live system.
run:
	./scripts/run-qemu.sh

run-uefi:
	./scripts/run-qemu.sh --uefi

# Rehearse a real install: UEFI + two blank 128 GB virtual SSDs.
run-install:
	./scripts/run-qemu.sh --uefi --disks

# Boot what was installed by run-install, without the ISO.
run-installed:
	./scripts/run-qemu.sh --uefi --installed

# Wipe the virtual SSDs and UEFI settings to start the install rehearsal over.
reset-vm:
	rm -rf build/vm

artwork:
	. config/os.conf && python3 scripts/make-artwork.py build/art "artwork/wallpapers/$$DEFAULT_WALLPAPER"

clean:
	sudo ./build.sh --clean

distclean:
	sudo ./build.sh --distclean
