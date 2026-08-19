"""Tests for resolve/assemble. No live network except optional skip."""

import os
import tempfile
import unittest

from plant import assemble
from plant import resolve
from sources import catalog_rest


class SisterNameTests(unittest.TestCase):
    def test_filters_genus(self):
        catalog = {
            "count": 4,
            "list": [
                "Acer campestre",
                "Digitalis grandiflora",
                "Digitalis lanata",
                "Digitalis lutea",
            ],
        }
        names = catalog_rest.sister_names("Digitalis", "Digitalis lanata", catalog)
        self.assertEqual(["Digitalis grandiflora", "Digitalis lutea"], names)
        self.assertEqual([], catalog_rest.sister_names("", "X", catalog))


class ApgPathTests(unittest.TestCase):
    def test_asterales_spine(self):
        path = resolve.apg_path("Asterales", "Asteraceae", "Bellis")
        self.assertEqual("Bellis", path["00_Genus"])
        self.assertEqual("Asteraceae", path["01_Familia"])
        self.assertEqual("Asterales", path["02_Ordo"])
        self.assertTrue(any(key.endswith("_Superregnum") for key in path))

    def test_photo_prefix(self):
        self.assertEqual("bp", resolve.photo_prefix("Bellis perennis"))
        self.assertEqual("ac", resolve.photo_prefix("Acer campestre"))


class TranslationTests(unittest.TestCase):
    def test_labels_and_german(self):
        resolved = {
            "accepted_name": "Bellis perennis",
            "labels": {"en": "daisy", "de": "Gänseblümchen"},
            "aliases": {"en": ["common daisy", "Bellis perennis"]},
            "wikipedia": {"en": "https://en.wikipedia.org/wiki/Bellis_perennis"},
            "synonyms": [{"name": "Bellis hortensis"}],
        }
        translations = assemble.translations_from_wikidata(resolved)
        self.assertEqual("daisy", translations["en"]["label"])
        self.assertIn("common daisy", translations["en"]["names"])
        self.assertNotIn("bellis perennis", translations["en"].get("names", []))
        self.assertEqual("Gänseblümchen", translations["de"]["label"])
        self.assertEqual(
            "https://en.wikipedia.org/wiki/Bellis_perennis",
            translations["en"]["wikipedia"],
        )


class AssembleTests(unittest.TestCase):
    def test_packet_needs_review_without_traits(self):
        resolved = {
            "query": "Bellis perennis",
            "accepted_name": "Bellis perennis",
            "author": "L.",
            "family": "Asteraceae",
            "order": "Asterales",
            "genus": "Bellis",
            "ipni_id": "184409-1",
            "gbif_id": "3117424",
            "usda_id": "BEPE2",
            "freebase_id": "/m/04c38s",
            "qid": "Q26158",
            "lifeform": "perennial",
            "l2": [10, 11, 12],
            "native_l2": [10, 11, 12],
            "wikilinks": {"data": "https://www.wikidata.org/wiki/Q26158"},
            "wikipedia": {},
            "labels": {"en": "daisy"},
            "aliases": {},
            "synonyms": [{"name": "Bellis hortensis", "authors": "Ten.", "ipni_id": "1"}],
            "apg": resolve.apg_path("Asterales", "Asteraceae", "Bellis"),
            "folder": "Asterales/Asteraceae/Bellis_perennis",
            "photo_prefix": "bp",
            "wiki_name": "Bellis perennis",
            "warnings": [],
        }
        packet = assemble.build_records(resolved, plant_id=69, already_in_catalog=True)
        self.assertEqual("needs_review", packet["job"]["status"])
        self.assertIn("color", packet["job"]["needs"])
        self.assertEqual("Asteraceae", packet["plants_header"]["family"])
        self.assertEqual([10, 11, 12], packet["plants_header"]["filterDistribution"])
        self.assertEqual([], packet["plants_header"]["filterColor"])
        self.assertEqual("184409-1", packet["plants_v2"]["ipniId"])
        self.assertEqual(3117424, packet["plants_v2"]["gbifId"])
        self.assertEqual("Bellis perennis", packet["plants_v2"]["wikiName"])
        self.assertTrue(
            packet["plants_v2"]["illustrationUrl"].endswith("Bellis_perennis.webp")
        )
        self.assertEqual(69, packet["plants_v2"]["id"])
        self.assertEqual("Bellis hortensis", packet["synonyms"]["ipni"][0]["name"])

    def test_writes_job_dir(self):
        resolved = {
            "query": "Fake plantus",
            "accepted_name": "Fake plantus",
            "author": "",
            "family": "Asteraceae",
            "order": "Asterales",
            "genus": "Fake",
            "ipni_id": "",
            "gbif_id": None,
            "usda_id": None,
            "freebase_id": None,
            "qid": None,
            "lifeform": "",
            "l2": [11],
            "native_l2": [11],
            "wikilinks": {},
            "wikipedia": {},
            "labels": {},
            "aliases": {},
            "synonyms": [],
            "apg": {},
            "folder": "Asterales/Asteraceae/Fake_plantus",
            "photo_prefix": "fp",
            "wiki_name": "Fake plantus",
            "warnings": [],
        }
        catalog = {"count": 1413, "list": ["Acer campestre"]}
        tmp = tempfile.TemporaryDirectory()
        try:
            dest = os.path.join(tmp.name, "Fake_plantus")
            packet = assemble.assemble(resolved, dest=dest, catalog=catalog)
            self.assertTrue(os.path.isfile(os.path.join(dest, "plants_v2.json")))
            self.assertTrue(os.path.isfile(os.path.join(dest, "review.md")))
            self.assertEqual(1413, packet["job"]["id"])
            self.assertFalse(packet["job"]["already_in_catalog"])
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
