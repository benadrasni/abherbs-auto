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
        self.assertEqual(
            "Acer_campestre_distribution.webp",
            media.distribution_map_name(
                "Sapindales/Sapindaceae/Acer_campestre/Acer_campestre.webp"
            ),
        )
        self.assertEqual(
            "Acer_campestre_distribution.webp",
            media.distribution_map_name("Acer_campestre@1600.webp"),
        )
        self.assertEqual(
            "Bellis_perennis_distribution.webp",
            media.distribution_map_name("", "Bellis perennis"),
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
            self.assertIn("last image as the page background", text)
            self.assertNotIn("#f4efe4", text)
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
            self.assertIn("last image as the page background", colorize)
            self.assertNotIn("#f4efe4", colorize)
            media.write_imagine_prompt(path, kind="generate")
            generate = open(path, encoding="utf-8").read()
            self.assertIn("Grok Imagine", generate)
            self.assertIn("last image as the page background", generate)
            self.assertNotIn("#f4efe4", generate)
            self.assertNotIn("colored by Grok Imagine", generate)
            self.assertNotIn("Keep the original composition", generate)
            self.assertNotIn("This plate is generated entirely by Imagine", generate)
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

    def _page(self, size, plant_box):
        image = media.apply_vignette(Image.new("RGB", size, media.CREAM))
        x0, y0, x1, y1 = plant_box
        for y in range(y0, y1):
            for x in range(x0, x1):
                image.putpixel((x, y), (40, 120, 40))
        return image

    def test_crop_letterbox_white_bars(self):
        page = self._page((200, 220), (70, 50, 130, 110))
        image = Image.new("RGB", (200, 300), (242, 238, 227))
        image.paste(page, (0, 40))
        cropped, bars = media.crop_letterbox(image)
        self.assertEqual((0, 40, 0, 40), bars)
        self.assertEqual((200, 220), cropped.size)
        self.assertEqual((40, 120, 40), cropped.getpixel((100, 70)))

    def test_crop_letterbox_black_surround(self):
        page = self._page((160, 240), (40, 80, 120, 140))
        image = Image.new("RGB", (200, 300), (10, 10, 10))
        image.paste(page, (20, 30))
        cropped, bars = media.crop_letterbox(image)
        self.assertEqual((20, 30, 20, 30), bars)
        self.assertEqual((160, 240), cropped.size)

    def test_crop_letterbox_noop_on_page(self):
        image = self._page((200, 300), (60, 80, 140, 160))
        cropped, bars = media.crop_letterbox(image)
        self.assertEqual((0, 0, 0, 0), bars)
        self.assertEqual((200, 300), cropped.size)

    def test_even_cream_spares_the_plant(self):
        image = Image.new("RGB", (200, 300), media.CREAM)
        burnt = (160, 148, 128)
        for y in range(12):
            for x in range(200):
                image.putpixel((x, y), burnt)
                image.putpixel((x, 299 - y), burnt)
        for y in range(80, 160):
            for x in range(60, 140):
                image.putpixel((x, y), (40, 130, 40))
        out = media.even_cream_border(image)
        self.assertEqual((40, 130, 40), out.getpixel((100, 120)))
        corner = out.getpixel((4, 4))
        self.assertGreater(sum(corner), sum(burnt))
        self.assertGreater(sum(corner), 500)

    def test_letterbox_fix_fills_23(self):
        page = self._page((200, 228), (80, 70, 120, 130))
        image = Image.new("RGB", (200, 300), (242, 238, 227))
        image.paste(page, (0, 36))
        out, bars = media.letterbox_fix(image, size=(200, 300))
        self.assertEqual((0, 36, 0, 36), bars)
        self.assertEqual((200, 300), out.size)
        self.assertNotEqual((242, 238, 227), out.getpixel((100, 4)))
        found = False
        for y in range(40, 260):
            if out.getpixel((100, y))[1] > 80 and out.getpixel((100, y))[1] > out.getpixel((100, y))[0]:
                found = True
                break
        self.assertTrue(found)

    def test_prepare_scan_pads_imagine_size(self):
        image = Image.new("RGB", (80, 140), (250, 250, 250))
        for y in range(10, 120):
            for x in range(80):
                image.putpixel((x, y), media.CREAM)
        for y in range(40, 80):
            for x in range(20, 60):
                image.putpixel((x, y), (20, 90, 20))
        out = media.prepare_scan(image)
        self.assertEqual(media.IMAGINE_PAD, out.size)
        self.assertGreater(sum(out.getpixel((2, 2))), 500)

    def test_stamp_signature_from_donor(self):
        donor = Image.new("RGB", (200, 300), media.CREAM)
        for x in range(140, 185):
            for y in range(282, 294):
                donor.putpixel((x, y), (90, 60, 30))
        target = Image.new("RGB", (200, 300), media.CREAM)
        for x in range(90, 198):
            for y in range(240, 298):
                target.putpixel((x, y), (70, 45, 25))
        for y in range(40, 120):
            for x in range(40, 100):
                target.putpixel((x, y), (30, 110, 30))
        out = media.stamp_signature(target, donor)
        self.assertEqual((30, 110, 30), out.getpixel((70, 80)))
        huge = target.getpixel((170, 270))
        cleared = out.getpixel((170, 270))
        self.assertGreater(sum(cleared), sum(huge))
        ink = False
        for y in range(250, 300):
            for x in range(150, 200):
                pixel = out.getpixel((x, y))
                if pixel[0] < 140 and pixel[0] > pixel[2]:
                    ink = True
                    break
            if ink:
                break
        self.assertTrue(ink)


if __name__ == "__main__":
    unittest.main()
