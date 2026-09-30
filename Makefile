.PHONY: deps build run run-uefi run-install run-installed reset-vm artwork assets maps test preview \
	try-settings try-scroll try-map clean distclean

HOST_PACKAGES = debootstrap debian-archive-keyring squashfs-tools xorriso apt-utils \
	grub-pc-bin grub-efi-amd64-bin mtools qemu-system-x86 qemu-utils ovmf python3-pil

PREVIEW = build/preview
# Run the desktop apps from the source tree with a throwaway home, so trying them on this PC
# never touches your real settings or Firefox.
TRY_ENV = HOME=$(CURDIR)/build/try-home WOF_DATA=$(CURDIR)/$(PREVIEW) \
	XDG_DATA_DIRS=$(CURDIR)/$(PREVIEW)/share:/usr/local/share:/usr/share PYTHONPATH=$(CURDIR)/desktop/lib

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
	. config/os.conf && wall=$$(sed -n 's/^default_wallpaper *= *"\([^"]*\)".*/\1/p' desktop/tribes/$$DEFAULT_TRIBE/tribe.toml) && \
	python3 scripts/make-artwork.py build/art "desktop/tribes/$$DEFAULT_TRIBE/wallpapers/$$wall"

# Generate every tribe's themes/icons/sounds into build/preview (what the build puts in /usr/share).
assets:
	rm -rf $(PREVIEW) && mkdir -p $(PREVIEW)
	cp -r desktop/tribes $(PREVIEW)/tribes
	ln -s ../../desktop/maps $(PREVIEW)/maps
	. config/os.conf && echo $$DEFAULT_TRIBE > $(PREVIEW)/default-tribe
	WOF_DATA=$(PREVIEW) PYTHONPATH=desktop/lib python3 -m pyrrhia.cli build-assets $(PREVIEW)/share \
		--tribes-dir $(PREVIEW)/tribes

# Re-export Pyrrhia from the 3D map, re-trace Pantala and rebuild the 3D viewers into desktop/maps.
# Needs node/npm; the results are committed, so a normal build doesn't run this.
maps:
	./scripts/import-maps.sh

test:
	PYTHONPATH=desktop/lib python3 -m unittest discover -s tests -v

# Contact sheet of all tribes' icons, wallpapers and terminal colours.
preview: assets
	WOF_DATA=$(PREVIEW) python3 scripts/preview-assets.py $(PREVIEW)/share $(PREVIEW)/tribes $(PREVIEW)/tribes.png
	@echo "Wrote $(PREVIEW)/tribes.png"

try-settings: assets
	$(TRY_ENV) python3 -m pyrrhia.settings_app

try-scroll: assets
	$(TRY_ENV) python3 -m wofscroll.app

try-map: assets
	$(TRY_ENV) python3 -m wofmap.app

clean:
	sudo ./build.sh --clean

distclean:
	sudo ./build.sh --distclean
