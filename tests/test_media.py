"""Illustration + photo-role tests. No Firebase."""

import os
import tempfile
import unittest

from PIL import Image

from plant import media
from plant import photo_roles
from sources import botanical_illustrations
from sources import commons


INGEST_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT = os.path.join(INGEST_ROOT, "fixtures", "botanical")


class BotanicalParseTests(unittest.TestCase):
    def test_search_picks_accepted_species(self):
        html = open(os.path.join(BOT, "search_acer_campestre.html"), encoding="utf-8").read()
        hits = botanical_illustrations.parse_search(html, "Acer campestre")
        self.assertTrue(hits)
        top = botanical_illustrations.pick_species(hits)
        self.assertEqual(8838, top["id_species"])
        self.assertGreaterEqual(top["plate_count"], 40)

    def test_gallery_skips_broken_thumbs(self):
        html = open(os.path.join(BOT, "species_8838.html"), encoding="utf-8").read()
        plates = botanical_illustrations.parse_species_gallery(html)
        ids = [item["id_illustration"] for item in plates]
        self.assertIn(48131, ids)
        self.assertNotIn(0, ids)

    def test_hd_src(self):
        html = open(os.path.join(BOT, "illustration_48131.html"), encoding="utf-8").read()
        src = botanical_illustrations.parse_hd_src(html)
        self.assertIsNotNone(src)
        self.assertIn("ILLUSTRATIONS_HD", src)
        self.assertTrue(src.endswith("48131.jpg"))


class CommonsLicenseTests(unittest.TestCase):
    def test_allow_and_deny(self):
        self.assertTrue(commons.license_ok("CC BY-SA 4.0"))
        self.assertTrue(commons.license_ok("Public domain"))
        self.assertTrue(commons.license_ok("CC0"))
        self.assertFalse(commons.license_ok("CC BY-NC 2.0"))
        self.assertFalse(commons.license_ok("CC BY-ND 3.0"))
        self.assertFalse(commons.license_ok(""))

    def test_license_urls(self):
        self.assertTrue(commons.license_ok_url("http://creativecommons.org/licenses/by/4.0/"))
        self.assertTrue(commons.license_ok_url("https://creativecommons.org/publicdomain/zero/1.0/"))
        self.assertFalse(commons.license_ok_url("http://creativecommons.org/licenses/by-nc/4.0/"))

    def test_role_for_category(self):
        self.assertEqual("flower", commons.role_for_category("Category:Bellis perennis (flowers)"))
        self.assertEqual("leaf", commons.role_for_category("Category:Bellis perennis leaves"))
        self.assertEqual("fruit", commons.role_for_category("Category:Bellis perennis (fruit)"))
        self.assertEqual("habit", commons.role_for_category("Category:Bellis perennis (habitat)"))
        self.assertIsNone(commons.role_for_category("Category:Bellis perennis (herbarium specimens)"))
        self.assertIsNone(commons.role_for_category("Category:Bellis perennis (cultivars)"))
        self.assertIsNone(commons.role_for_category("Category:Bellis perennis - botanical illustrations"))

    def test_reject_maps_and_cultivars(self):
        self.assertTrue(commons.rejected_title("File:Bellis perennis range map.svg"))
        self.assertTrue(commons.rejected_title("File:Bellis perennis 'Habanero Red' Flower.jpg"))
        self.assertFalse(commons.rejected_title("File:Bellis perennis – Flower.jpg"))


class PhotoRoleTests(unittest.TestCase):
    def test_named_slots(self):
        files = [
            {"path": "3-fruit.jpg"},
            {"path": "1-flower.jpg"},
            {"path": "2-leaf.jpg"},
            {"path": "4-habit.jpg"},
        ]
        packed = photo_roles.pack(files)
        self.assertEqual("ok", packed["status"])
        self.assertEqual(
            ["flower", "leaf", "fruit", "habit"],
            [item["role"] for item in packed["photos"]],
        )

    def test_keywords_and_minimum(self):
        files = [
            {"title": "File:Plant flower.jpg", "description": "the flower"},
            {"title": "File:Plant leaf.jpg", "description": "a leaf"},
        ]
        packed = photo_roles.pack(files)
        self.assertEqual("needs_review", packed["status"])
        self.assertEqual("flower", packed["photos"][0]["role"])

    def test_no_flower(self):
        packed = photo_roles.pack([{"title": "leaf only.jpg", "description": "leaf"}])
        self.assertEqual("needs_review", packed["status"])
        self.assertEqual([], packed["photos"])

    def test_skip_fruit_when_missing(self):
        packed = photo_roles.pack(
            [
                {"path": "1-flower.jpg"},
                {"path": "2-leaf.jpg"},
                {"path": "4-habit.jpg"},
            ]
        )
        self.assertEqual("ok", packed["status"])
        self.assertEqual(
            ["flower", "leaf", "habit"],
            [item["role"] for item in packed["photos"]],
        )
        self.assertIn("fruit", packed.get("skipped") or [])

    def test_commons_requires_species_name(self):
        self.assertTrue(
            commons.matches_species(
                {"title": "File:Digitalis lanata fruit.jpg"},
                "Digitalis lanata",
            )
        )
        self.assertFalse(
            commons.matches_species(
                {"title": "File:Eucomis comosa 005.JPG"},
                "Digitalis lanata",
            )
        )

    def test_role_hint_wins(self):
        packed = photo_roles.pack(
            [
                {"title": "mystery.jpg", "role_hint": "flower", "score": 9},
                {"title": "also.jpg", "role_hint": "leaf", "score": 3},
                {"title": "fruit.jpg", "role_hint": "fruit", "score": 2},
            ]
        )
        self.assertEqual("ok", packed["status"])
        self.assertEqual(
            ["flower", "leaf", "fruit"],
            [item["role"] for item in packed["photos"]],
        )

    def test_trunk_only_when_woody(self):
        files = [
            {"path": "1-flower.jpg"},
            {"path": "2-leaf.jpg"},
            {"path": "3-fruit.jpg"},
            {"path": "5-trunk.jpg"},
        ]
        herb = photo_roles.pack(files, lifeform="perennial herb")
        self.assertNotIn("trunk", [item["role"] for item in herb["photos"]])
        tree = photo_roles.pack(files, lifeform="tree")
        self.assertIn("trunk", [item["role"] for item in tree["photos"]])


class CleanIllustrationTests(unittest.TestCase):
    def test_plate_paths_and_grid_url(self):
        paths = media.official_plate_paths("/tmp/Acer_campestre.webp")
        self.assertTrue(paths["master"].endswith("Acer_campestre@1600.webp"))
        self.assertTrue(paths["grid"].endswith("Acer_campestre@400.webp"))
        self.assertEqual("/tmp/Acer_campestre.webp", paths["alias"])
        self.assertEqual(
            "Acer_campestre@400.webp",
            media.grid_filename("Acer_campestre@1600.webp"),
        )
        self.assertIsNone(media.grid_filename("Acer_campestre.webp"))
        self.assertEqual(
            "Sapindales/Acer_campestre@400.webp",
            media.grid_url("Sapindales/Acer_campestre@1600.webp"),
        )
        self.assertEqual(
            ["Acer_campestre@1600.webp", "Acer_campestre@400.webp"],
            media.sibling_plate_filenames("Acer_campestre.webp"),
        )

    def test_cream_paper_becomes_2x3_plates(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            src = os.path.join(tmp.name, "plate.jpg")
            dest = os.path.join(tmp.name, "Acer_campestre@1600.webp")
            image = Image.new("RGB", (80, 120), (236, 228, 210))
            for x in range(20, 50):
                for y in range(20, 70):
                    image.putpixel((x, y), (40, 120, 40))
            image.save(src, "JPEG")
            written = media.clean_illustration(src, dest)
            self.assertEqual(dest, written)
            out = Image.open(dest)
            grid = Image.open(os.path.join(tmp.name, "Acer_campestre@400.webp"))
            self.assertEqual("WEBP", out.format)
            self.assertEqual((1600, 2400), out.size)
            self.assertEqual((400, 600), grid.size)
            self.assertEqual("RGB", out.mode)
            corner = out.getpixel((2, 2))
            self.assertNotEqual((255, 255, 255), corner)
            self.assertGreater(sum(corner), 500)
            self.assertLess(sum(corner), sum(media.CREAM))
        finally:
            tmp.cleanup()

    def test_imagine_import_does_not_recrop(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            src = os.path.join(tmp.name, "imagine.png")
            dest = os.path.join(tmp.name, "Plant@1600.webp")
            image = Image.new("RGB", (200, 300), media.CREAM)
            for x in range(8, 28):
                for y in range(8, 28):
                    image.putpixel((x, y), (30, 90, 30))
            for x in range(172, 192):
                for y in range(272, 292):
                    image.putpixel((x, y), (90, 30, 30))
            image.save(src, "PNG")
            media.import_imagine_result(src, dest)
            out = Image.open(dest)
            self.assertEqual((1600, 2400), out.size)
            self.assertLess(out.getpixel((80, 80))[0], 80)
            self.assertGreater(out.getpixel((1510, 2310))[0], 60)
        finally:
            tmp.cleanup()

    def test_imagine_prompts(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            path = os.path.join(tmp.name, "prompt.txt")
            media.write_imagine_prompt(path, kind="clean")
            text = open(path, encoding="utf-8").read()
            self.assertIn("#f4efe4", text)
            self.assertIn("Do not add a Grok signature", text)
            self.assertIn("leave the plate unsigned", text)
            self.assertNotIn("colored by Grok Imagine", text)
            media.write_imagine_prompt(path, kind="clean", author="J. Kops")
            named = open(path, encoding="utf-8").read()
            self.assertIn("J. Kops", named)
            self.assertIn("Ignore any signature", named)
            media.write_imagine_prompt(path, kind="colorize", author="J. Kops")
            colorize = open(path, encoding="utf-8").read()
            self.assertIn("colored by Grok Imagine", colorize)
            self.assertIn("J. Kops", colorize)
            media.write_imagine_prompt(path, kind="generate")
            generate = open(path, encoding="utf-8").read()
            self.assertIn("Grok Imagine", generate)
            self.assertNotIn("colored by Grok Imagine", generate)
        finally:
            tmp.cleanup()

    def test_author_from_plate_title(self):
        from sources import botanical_illustrations

        self.assertEqual(
            "J. Kops",
            botanical_illustrations.author_from_plate_title(
                "Acer campestre L. / J. Kops, Fl. Bat., vol. 15 : t. 1166 (1877)"
            ),
        )
        self.assertEqual("", botanical_illustrations.author_from_plate_title("Acer campestre L."))

    def test_photo_square(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            src = os.path.join(tmp.name, "in.jpg")
            out = os.path.join(tmp.name, "a.webp")
            thumb = os.path.join(tmp.name, "t.webp")
            Image.new("RGB", (100, 60), (10, 80, 10)).save(src, "JPEG")
            media.process_photo(src, out, thumb)
            self.assertEqual((512, 512), Image.open(out).size)
            self.assertEqual((128, 128), Image.open(thumb).size)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
