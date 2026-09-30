import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPS = ROOT / "desktop/maps"
os.environ.setdefault("WOF_DATA", str(ROOT / "build/preview"))

from wofmap import atlas  # noqa: E402


class ContinentData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.continents = {c.id: c for c in atlas.all_continents(MAPS)}

    def test_both_continents_load_in_order(self):
        self.assertEqual(list(self.continents)[:2], ["pyrrhia", "pantala"])
        for c in self.continents.values():
            self.assertTrue(c.relief_path.is_file(), c.id)
            self.assertTrue(c.height_path.is_file(), c.id)
            self.assertTrue(c.land and c.landmarks, c.id)

    def test_landmarks_are_inside_the_frame_with_known_groups(self):
        for c in self.continents.values():
            groups = {g["id"] for g in c.groups}
            ids = [m.id for m in c.landmarks]
            self.assertEqual(len(ids), len(set(ids)), f"{c.id}: duplicate landmark ids")
            for m in c.landmarks:
                self.assertTrue(0 <= m.pos[0] <= 1 and 0 <= m.pos[1] <= 1, m.id)
                self.assertIn(m.group, groups, m.id)
                self.assertIn(m.rank, (1, 2, 3), m.id)

    def test_pantala_hives_sit_on_land_in_the_savanna(self):
        pantala = self.continents["pantala"]
        hives = [m for m in pantala.landmarks if m.group == "hive"]
        self.assertEqual(len(hives), 9)
        for hive in hives:
            self.assertTrue(atlas.on_land(pantala, *hive.pos), hive.name)
            self.assertEqual(pantala.region_at(*hive.pos).id, "savanna", hive.name)

    def test_pantala_scale_matches_the_books(self):
        pantala = self.continents["pantala"]
        miles = pantala.distance_miles(pantala.landmark("cicada-hive").pos, pantala.landmark("wasp-hive").pos)
        self.assertAlmostEqual(miles, 600, delta=5)
        self.assertIn("2.5 days", atlas.flight_time(miles))

    def test_pyrrhia_regions_and_lakes(self):
        pyrrhia = self.continents["pyrrhia"]
        self.assertEqual(pyrrhia.region_at(*pyrrhia.landmark("IceWing Palace").pos).id, "ice")
        sea = next(r for r in pyrrhia.regions if r.id == "sea")
        self.assertEqual(sea.polygon, [])
        self.assertIsNotNone(sea.anchor)
        self.assertTrue(pyrrhia.lakes)

    def test_pantala_named_lakes(self):
        names = {l["name"] for l in self.continents["pantala"].lakes}
        self.assertTrue({"Beetle Lake", "Lake Scorpion"} <= names)

    def test_region_anchors_land_inside_their_regions(self):
        pantala = self.continents["pantala"]
        atlas.region_anchors(pantala, lambda x, y: atlas.on_land(pantala, x, y), steps=40)
        for r in pantala.regions:
            self.assertIsNotNone(r.anchor, r.id)
            self.assertTrue(atlas.point_in_polygon(*r.anchor, r.polygon), r.id)

    def test_3d_sources(self):
        self.assertTrue(self.continents["pyrrhia"].own_3d)
        self.assertFalse(self.continents["pantala"].own_3d)
        self.assertTrue((MAPS / "viewer/index.html").is_file())
        self.assertTrue((MAPS / "viewer/viewer.js").is_file())


class Helpers(unittest.TestCase):
    def test_height_field_decodes_red_green(self):
        # 2x1 RGB image: 1000 m + 1000 offset = 2000 = 0x07D0, then sea floor at -500.
        pixels = bytes([0x07, 0xD0, 0, 0x01, 0xF4, 0])
        field = atlas.HeightField(pixels, 2, 1, 6, 3)
        self.assertEqual(field.metres(0.0, 0.5), 1000)
        self.assertEqual(field.metres(1.0, 0.5), -500)

    def test_formatting(self):
        self.assertEqual(atlas.format_height(0), "sea level")
        self.assertEqual(atlas.format_height(1000), "1,000 m (3,281 ft)")
        self.assertEqual(atlas.format_miles(1234.4), "1,234 miles")
        self.assertEqual(atlas.flight_time(240), "about a day\u2019s flight")
        self.assertIn("hour", atlas.flight_time(30))
        miles, px = atlas.nice_scale(3.7)
        self.assertIn(miles, (100, 200, 500, 1000))
        self.assertAlmostEqual(px, miles / 3.7)

    def test_bad_map_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "broken").mkdir()
            (Path(tmp) / "broken/map.json").write_text("{not json")
            self.assertEqual(atlas.all_continents(tmp), [])


class SchemeResolution(unittest.TestCase):
    def setUp(self):
        try:
            from wofmap import view3d
        except (ImportError, ValueError) as e:
            self.skipTest(f"GTK not available: {e}")
        self.view3d = view3d

    def test_serves_files_inside_the_maps_folder_only(self):
        resolve = self.view3d.resolve
        self.assertEqual(resolve(MAPS, "/viewer/index.html"), (MAPS / "viewer/index.html").resolve())
        self.assertIsNone(resolve(MAPS, "/../pantala/../../README.md"))
        self.assertIsNone(resolve(MAPS, "/../../../etc/passwd"))
        self.assertIsNone(resolve(MAPS, "/viewer/missing.js"))

    def test_urls_and_focus_scripts(self):
        continents = {c.id: c for c in atlas.all_continents(MAPS)}
        pyrrhia, pantala = continents["pyrrhia"], continents["pantala"]
        self.assertEqual(self.view3d.url_for(pyrrhia), "wofmap://maps/pyrrhia/3d/index.html")
        self.assertEqual(self.view3d.url_for(pantala), "wofmap://maps/viewer/index.html?map=pantala")
        script = self.view3d.focus_script(pyrrhia, pyrrhia.landmark("Queen Moorhen\u2019s Lake")
                                          or pyrrhia.landmarks[0])
        self.assertIn(".lm-btn", script)
        tricky = atlas.Landmark("x", 'Say "hi"\u2019s </script>', "", (0.5, 0.5), "hive", 1)
        self.assertIn('"Say \\"hi\\"', self.view3d.focus_script(pyrrhia, tricky))
        self.assertIn('wofFocus', self.view3d.focus_script(pantala, pantala.landmarks[0]))


if __name__ == "__main__":
    unittest.main()
