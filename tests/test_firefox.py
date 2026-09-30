import os
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

USER_JS = 'user_pref("browser.startup.homepage", "https://example.com");\n'
USER_CHROME = "#TabsToolbar { color: red; }\n"


class FirefoxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "home"
        self.saved = {k: os.environ.get(k) for k in ("WOF_DATA", "HOME", "XDG_CONFIG_HOME")}
        os.environ.update(WOF_DATA=str(REPO / "desktop"), HOME=str(self.home))
        os.environ.pop("XDG_CONFIG_HOME", None)
        import importlib
        from pyrrhia import firefox, paths, tribes
        importlib.reload(paths)
        importlib.reload(tribes)
        self.firefox = importlib.reload(firefox)
        self.tribe = tribes.load(REPO / "desktop/tribes/nightwing")
        self.other = tribes.load(REPO / "desktop/tribes/skywing")

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp)

    def make_profile(self):
        root = self.home / ".mozilla/firefox"
        profile = root / "abc.default-esr"
        (profile / "chrome").mkdir(parents=True)
        (root / "profiles.ini").write_text(
            "[Profile0]\nName=default-esr\nIsRelative=1\nPath=abc.default-esr\nDefault=1\n")
        (profile / "user.js").write_text(USER_JS)
        (profile / "chrome/userChrome.css").write_text(USER_CHROME)
        return profile

    def test_keeps_users_settings(self):
        profile = self.make_profile()
        self.firefox.apply(self.tribe)
        self.firefox.apply(self.other)
        user_js = (profile / "user.js").read_text()
        self.assertTrue(user_js.startswith(USER_JS))
        self.assertEqual(user_js.count("BEGIN Wings of Fire OS"), 1)
        self.assertIn('"skywing"', user_js)
        chrome = (profile / "chrome/userChrome.css").read_text()
        self.assertTrue(chrome.startswith("@import"))
        self.assertIn(USER_CHROME, chrome)
        self.assertEqual(chrome.count("@import"), 1)

    def test_remove_restores_original(self):
        profile = self.make_profile()
        self.firefox.apply(self.tribe)
        self.firefox.remove()
        self.assertEqual((profile / "user.js").read_text(), USER_JS)
        self.assertEqual((profile / "chrome/userChrome.css").read_text(), USER_CHROME)
        self.assertFalse((profile / "chrome/wof-tribe.css").exists())
        self.assertFalse((profile / "chrome/userContent.css").exists())

    def test_creates_profile_when_none(self):
        touched = self.firefox.apply(self.tribe)
        self.assertEqual(len(touched), 1)
        self.assertTrue((touched[0] / "chrome/wof-tribe.css").exists())
        self.assertIn("Default=1", (self.home / ".mozilla/firefox/profiles.ini").read_text())


if __name__ == "__main__":
    unittest.main()
