import configparser
import shutil
import tempfile
import unittest
import wave
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyrrhia import assets, tribes
        cls.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(REPO / "desktop/tribes", cls.tmp / "tribes")
        cls.tribes = [tribes.load(d) for d in sorted((cls.tmp / "tribes").iterdir())]
        assets.build_all(cls.tmp / "share", cls.tribes, tribes_dir=cls.tmp / "tribes")
        cls.share = cls.tmp / "share"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_every_tribe_has_a_wallpaper(self):
        for tribe in self.tribes:
            self.assertTrue(list((self.tmp / "tribes" / tribe.id / "wallpapers").iterdir()), tribe.id)

    def test_svgs_are_well_formed(self):
        svgs = list(self.share.glob("icons/**/*.svg")) + list(self.tmp.glob("tribes/*/wallpapers/*.svg"))
        self.assertGreater(len(svgs), 100)
        for svg in svgs:
            ET.parse(svg)

    def test_style_schemes_are_well_formed(self):
        for tribe in self.tribes:
            for name in (f"wof-{tribe.id}.xml", f"wof-parchment-{tribe.id}.xml"):
                root = ET.parse(self.share / "gtksourceview-4/styles" / name).getroot()
                self.assertEqual(root.tag, "style-scheme")

    def test_sounds_are_valid_wavs(self):
        for tribe in self.tribes:
            path = self.share / "sounds" / tribe.sound_theme / "stereo/desktop-login.wav"
            with wave.open(str(path)) as w:
                self.assertGreater(w.getnframes(), 1000)

    def test_theme_indexes_parse(self):
        for tribe in self.tribes:
            for index in (self.share / "themes" / tribe.theme_name / "index.theme",
                          self.share / "icons" / tribe.icon_theme / "index.theme",
                          self.share / "sounds" / tribe.sound_theme / "index.theme"):
                parser = configparser.ConfigParser()
                parser.read(index)
                self.assertTrue(parser.sections(), index)

    def test_terminal_palette_has_16_colours(self):
        from pyrrhia.assets import terminal
        for tribe in self.tribes:
            self.assertEqual(len(terminal.colours(tribe)["color-palette"].split(";")), 16)

    def test_gtk_css_loads(self):
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk
        except (ImportError, ValueError):
            self.skipTest("GTK not available")
        for tribe in self.tribes:
            for css in ("gtk-3.0/gtk.css", "xfce-notify-4.0/gtk.css"):
                provider = Gtk.CssProvider()
                provider.load_from_path(str(self.share / "themes" / tribe.theme_name / css))


if __name__ == "__main__":
    unittest.main()
