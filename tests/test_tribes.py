import os
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TribeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        shutil.copytree(REPO / "desktop/tribes", self.data / "tribes")
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {k: os.environ.get(k) for k in ("WOF_DATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME")}
        os.environ.update(WOF_DATA=str(self.data), HOME=str(self.home))
        os.environ.pop("XDG_DATA_HOME", None)
        os.environ.pop("XDG_CONFIG_HOME", None)
        import importlib
        from pyrrhia import paths, tribes
        importlib.reload(paths)
        importlib.reload(tribes)
        self.tribes = tribes
        self.paths = paths

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp)

    def test_all_ten_tribes_load(self):
        found = self.tribes.all_tribes()
        self.assertEqual(set(found), {"skywing", "seawing", "icewing", "sandwing", "nightwing", "rainwing",
                                      "mudwing", "leafwing", "hivewing", "silkwing"})

    def test_user_wallpapers_ship(self):
        self.assertEqual(self.tribes.get("seawing").wallpaper().name, "turtle.png")
        self.assertEqual(self.tribes.get("rainwing").wallpaper().name, "glory.png")
        self.assertEqual(self.tribes.get("sandwing").wallpaper().name, "sunny.png")

    def test_user_can_add_wallpapers_to_a_system_tribe(self):
        extra = self.home / ".local/share/wingsoffire/tribes/icewing/wallpapers"
        extra.mkdir(parents=True)
        (extra / "frost.png").write_bytes(b"not really a png")
        ice = self.tribes.get("icewing")
        self.assertIn("frost.png", [p.name for p in ice.wallpapers()])
        self.assertTrue(ice.has_own_wallpaper())

    def test_user_can_add_a_new_tribe(self):
        tribe_dir = self.home / ".local/share/wingsoffire/tribes/animus"
        tribe_dir.mkdir(parents=True)
        (tribe_dir / "tribe.toml").write_text(
            'name = "Animus"\npattern = "stars"\n[colors]\naccent = "#ff00ff"\naccent_alt = "#00ffff"\n'
            'background = "#000000"\nsurface = "#111111"\ntext = "#ffffff"\n')
        animus = self.tribes.get("animus")
        self.assertEqual(animus.theme_name, "WoF-Animus")
        self.assertTrue(animus.editor["seal"].startswith("#"))

    def test_bad_tribe_is_reported(self):
        bad = self.data / "tribes/broken"
        bad.mkdir()
        (bad / "tribe.toml").write_text('name = "Broken"\n[colors]\naccent = "red"\n')
        with self.assertRaises(self.tribes.TribeError):
            self.tribes.load(bad)
        self.assertNotIn("broken", self.tribes.all_tribes())
        self.assertIn("seawing", self.tribes.all_tribes())

    def test_placeholders_sort_last(self):
        walls = self.data / "tribes/seawing/wallpapers"
        (walls / "placeholder.svg").write_text("<svg/>")
        self.assertEqual(self.tribes.get("seawing").wallpapers()[-1].name, "placeholder.svg")
        self.assertEqual(self.tribes.get("seawing").wallpaper().name, "turtle.png")


if __name__ == "__main__":
    unittest.main()
