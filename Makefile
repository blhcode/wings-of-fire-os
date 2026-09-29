.PHONY: deps build run run-uefi wallpaper clean distclean

HOST_PACKAGES = debootstrap debian-archive-keyring squashfs-tools xorriso \
	grub-pc-bin grub-efi-amd64-bin mtools qemu-system-x86 ovmf python3-pil

deps:
	sudo apt-get install -y $(HOST_PACKAGES)

build:
	sudo ./build.sh

run:
	./scripts/run-qemu.sh

run-uefi:
	./scripts/run-qemu.sh --uefi

wallpaper:
	. config/os.conf && python3 scripts/make-wallpaper.py build/art "$$OS_NAME"

clean:
	sudo ./build.sh --clean

distclean:
	sudo ./build.sh --distclean
