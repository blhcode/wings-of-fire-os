import importlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent


class FakeXfconf:
    """Stands in for xfconf-query and xrandr."""

    def __init__(self, props=None, monitors=("Virtual-1",), workspaces=2):
        self.props = dict(props or {})
        self.monitors = list(monitors)
        self.workspaces = workspaces

    def patch(self, system):
        return mock.patch.multiple(
            system,
            xfconf_list=lambda channel: list(self.props) if channel == "xfce4-desktop" else [],
            xfconf_get=lambda channel, prop, default=None: str(self.workspaces),
            xfconf_set=lambda channel, prop, value: self.props.__setitem__(prop, value),
            monitor_names=lambda: self.monitors,
        )

    def images(self):
        return {k: v for k, v in self.props.items() if k.endswith("/last-image")}


class WallpaperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        share = self.tmp / "share"
        self.data = share / "wingsoffire"
        shutil.copytree(REPO / "desktop/tribes", self.data / "tribes")
        self.backgrounds = share / "backgrounds/wingsoffire"
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {k: os.environ.get(k) for k in ("WOF_DATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME")}
        os.environ.update(WOF_DATA=str(self.data), HOME=str(self.home))
        os.environ.pop("XDG_DATA_HOME", None)
        os.environ.pop("XDG_CONFIG_HOME", None)
        from pyrrhia import components, paths, state, system, theme, tribes
        for module in (paths, tribes, state, components, theme):
            importlib.reload(module)
        self.components, self.system, self.theme, self.state = components, system, theme, state
        self.tribe = tribes.get("icewing")
        self.wall = self.tribe.wallpaper()

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp)

    def link_all_wallpapers(self):
        """What hooks/15-tribes.sh does at build time."""
        self.backgrounds.mkdir(parents=True)
        for tribe_dir in (self.data / "tribes").iterdir():
            for wall in (tribe_dir / "wallpapers").iterdir():
                (self.backgrounds / f"{tribe_dir.name}-{wall.name}").symlink_to(wall)

    def test_sets_every_monitor_and_workspace(self):
        fake = FakeXfconf(monitors=["Virtual-1", "HDMI-1"], workspaces=3)
        with fake.patch(self.system):
            self.components.wallpaper(self.tribe, self.wall)
        self.assertEqual(len(fake.images()), 6)
        self.assertEqual(set(fake.images().values()), {str(self.wall)})

    def test_uses_the_shared_backgrounds_folder_so_xfce_lists_every_tribe(self):
        self.link_all_wallpapers()
        fake = FakeXfconf()
        with fake.patch(self.system):
            self.components.wallpaper(self.tribe, self.wall)
        shown = Path(next(iter(fake.images().values())))
        self.assertEqual(shown.parent, self.backgrounds)
        self.assertEqual(shown.resolve(), self.wall.resolve())
        self.assertGreater(len(list(shown.parent.iterdir())), len(self.tribe.wallpapers()))

    def test_login_keeps_a_wallpaper_picked_in_xfce_settings(self):
        picked = "/usr/share/backgrounds/wingsoffire/skywing-peril-escaping-peril.jpg"
        fake = FakeXfconf({"/backdrop/screen0/monitorVirtual-1/workspace0/last-image": picked})
        self.state.save(self.state.State(tribe="icewing"))
        with fake.patch(self.system), mock.patch.object(self.components, "firefox", lambda t, w: ""):
            importlib.reload(self.theme)
            self.theme.session_start()
        images = fake.images()
        self.assertEqual(images["/backdrop/screen0/monitorVirtual-1/workspace0/last-image"], picked)
        self.assertEqual(images["/backdrop/screen0/monitorVirtual-1/workspace1/last-image"], str(self.wall))


try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk  # noqa: F401
    HAVE_GTK = True
except (ImportError, ValueError):
    HAVE_GTK = False


@unittest.skipUnless(HAVE_GTK, "needs GTK 3")
class WelcomeTests(unittest.TestCase):
    def test_welcome_opens_only_on_first_login(self):
        from pyrrhia import settings_app
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home)
        opened = []

        class FakeApp:
            def __init__(self, welcome=False):
                self.welcome = welcome

            def run(self, argv):
                opened.append((self.welcome, argv))
                return 0

        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(home)}), \
                mock.patch.object(settings_app, "SettingsApp", FakeApp), \
                mock.patch.object(settings_app.sys, "argv", ["pyrrhia-settings", "--welcome"]):
            settings_app.main()
            settings_app.main()
        self.assertEqual(opened, [(True, ["pyrrhia-settings"])])


if __name__ == "__main__":
    unittest.main()
