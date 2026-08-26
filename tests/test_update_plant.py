"""Offline tests for scripts.update_plant catalog resolution."""

import os
import unittest

from scripts import update_plant


CATALOG = {
    "count": 4,
    "list": [
        "Acer campestre",
        "Arnica montana",
        "Potentilla anserina",
        "Anemone narcissiflora",
    ],
}


class ResolveCatalogTests(unittest.TestCase):
    def test_index(self):
        hit = update_plant.resolve_catalog(1, CATALOG, lookup=lambda name: None)
        self.assertEqual(1, hit["id"])
        self.assertEqual("Arnica montana", hit["name"])

    def test_index_out_of_range(self):
        self.assertIsNone(
            update_plant.resolve_catalog(99, CATALOG, lookup=lambda name: None)
        )

    def test_exact_name(self):
        hit = update_plant.resolve_catalog(
            "Arnica montana", CATALOG, lookup=lambda name: None
        )
        self.assertEqual(1, hit["id"])
        self.assertEqual("Arnica montana", hit["name"])

    def test_case_insensitive(self):
        hit = update_plant.resolve_catalog(
            "arnica MONTANA", CATALOG, lookup=lambda name: None
        )
        self.assertEqual("Arnica montana", hit["name"])

    def test_wcvp_accepted_maps_to_catalog_key(self):
        def lookup(name):
            return {
                "query_name": name,
                "accepted_name": "Potentilla anserina",
            }

        hit = update_plant.resolve_catalog("Argentina anserina", CATALOG, lookup=lookup)
        self.assertEqual(2, hit["id"])
        self.assertEqual("Potentilla anserina", hit["name"])
        self.assertEqual("Potentilla anserina", hit["wcvp_accepted"])

    def test_catalog_key_not_wcvp_accepted(self):
        def lookup(name):
            return {
                "query_name": "Anemone narcissiflora",
                "accepted_name": "Anemonastrum narcissiflorum",
            }

        hit = update_plant.resolve_catalog(
            "Anemonastrum narcissiflorum", CATALOG, lookup=lookup
        )
        self.assertEqual("Anemone narcissiflora", hit["name"])
        self.assertIn("do not rename", hit["note"])

    def test_missing(self):
        self.assertIsNone(
            update_plant.resolve_catalog(
                "Digitalis parviflora", CATALOG, lookup=lambda name: None
            )
        )


class PathsTests(unittest.TestCase):
    def test_job_dir_and_slug(self):
        path = update_plant.job_dir(56, "Arnica montana")
        self.assertEqual("56_Arnica_montana", os.path.basename(path))
        self.assertEqual("_update", os.path.basename(os.path.dirname(path)))
        self.assertTrue(path.endswith("plants/_jobs/_update/56_Arnica_montana"))

    def test_parse_item(self):
        self.assertEqual(56, update_plant.parse_item("56"))
        self.assertEqual("Arnica montana", update_plant.parse_item("Arnica montana"))
