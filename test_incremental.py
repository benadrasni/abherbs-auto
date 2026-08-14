"""Incremental index and APG tree tests. No Firebase."""

import unittest

import apg_tree
import catalog_indexes
import incremental_indexes


class FilterPatchTests(unittest.TestCase):
    def test_matches_matching_keys(self):
        header = {
            "filterColor": [5, 2],
            "filterHabitat": [6],
            "filterPetal": [2],
            "filterDistribution": [10, 11],
        }
        patch = incremental_indexes.filter_patch(0, header)
        keys = catalog_indexes.matching_keys(header)
        self.assertEqual(set(keys), set(patch["counts"]))
        self.assertEqual(1, patch["counts"]["5_6_2_10"])
        self.assertEqual({"0": 1}, patch["lists"]["2_6_2_11"])
        self.assertIn("___", patch["counts"])


class SearchPhotoPatchTests(unittest.TestCase):
    def test_search_and_photo(self):
        translations = {"en": {"label": "field maple", "names": ["hedge maple"]}}
        search = incremental_indexes.search_patch(
            0, translations, "Acer campestre", [{"name": "Euacer campestre"}]
        )
        self.assertIn("field maple", search["search"]["en"])
        self.assertTrue(search["search"]["en"]["field maple"].get("is_label"))
        self.assertIn("acer campestre", search["search"]["la"])

    def test_skips_illegal_search_chars(self):
        search = incremental_indexes.search_patch(
            7,
            {"es": {"label": "azucena", "names": ["lilium carniolicum ssp. jankae"]}},
            "Lilium pyrenaicum",
        )
        self.assertIn("azucena", search["search"]["es"])
        self.assertNotIn("lilium carniolicum ssp. jankae", search["search"]["es"])
        self.assertTrue(any("illegal search key" in item for item in search["warnings"]))
        photo = incremental_indexes.photo_patch(
            "Acer campestre", [{"name": "Euacer campestre"}], "/m/028j7f"
        )
        self.assertEqual("Acer campestre", photo["acer campestre"]["path"])
        self.assertIn("028j7f", photo["m"])


def _digitalis_family():
    return {
        "type": "Familia",
        "count": 3,
        "list": {"170": 1, "171": 1, "172": 1},
        "Digitalideae": {
            "type": "Tribus",
            "count": 3,
            "list": {"170": 1, "171": 1, "172": 1},
            "Digitalis": {
                "type": "Genus",
                "count": 3,
                "list": {"170": 1, "171": 1, "172": 1},
                "freebase": "/m/028f4",
                "Digitalis": {
                    "type": "Sectio",
                    "count": 1,
                    "list": {"172": 1},
                },
                "Grandiflorae": {
                    "type": "Sectio",
                    "count": 1,
                    "list": {"170": 1},
                },
            },
        },
    }


class ApgTests(unittest.TestCase):
    def test_inserts_id_along_path(self):
        apg = {
            "00_Genus": "Acer",
            "01_Familia": "Sapindaceae",
            "02_Ordo": "Sapindales",
            "03_Cladus": "Malvids",
            "10_Regnum": "Plantae",
            "11_Superregnum": "Eukaryota",
        }
        tree = {}
        result = apg_tree.apply_plant(tree, apg, 0)
        self.assertIn("Eukaryota", result["created"])
        self.assertIn("Acer", result["created"])
        node = tree["Eukaryota"]["Plantae"]["Malvids"]["Sapindales"]["Sapindaceae"]["Acer"]
        self.assertEqual({"0": 1}, node["list"])
        self.assertEqual(1, node["count"])
        self.assertEqual("Genus", node["type"])
        self.assertEqual(1, tree["Eukaryota"]["count"])

    def test_reuses_nested_genus_instead_of_sibling(self):
        family = _digitalis_family()
        tree = {"Plantaginaceae": family}
        apg = {
            "00_Genus": "Digitalis",
            "01_Familia": "Plantaginaceae",
        }
        result = apg_tree.apply_plant(tree, apg, 1413)
        self.assertNotIn("Digitalis", family)
        genus = family["Digitalideae"]["Digitalis"]
        self.assertEqual(1, genus["list"]["1413"])
        self.assertEqual(4, genus["count"])
        self.assertEqual(4, family["Digitalideae"]["count"])
        self.assertEqual(1, family["list"]["1413"])
        self.assertIn(("Tribus", "Digitalideae"), result["path"])
        self.assertIn(("Genus", "Digitalis"), result["path"])
        self.assertNotIn("Digitalis", result["created"])

    def test_prefers_classified_genus_over_stray(self):
        family = _digitalis_family()
        family["Digitalis"] = {
            "type": "Genus",
            "count": 1,
            "list": {"1413": 1},
        }
        result = apg_tree.apply_plant(
            {"Plantaginaceae": family},
            {"00_Genus": "Digitalis", "01_Familia": "Plantaginaceae"},
            1413,
        )
        self.assertEqual(4, family["Digitalideae"]["Digitalis"]["count"])
        self.assertEqual({"1413": 1}, family["Digitalis"]["list"])
        self.assertEqual(
            ("Genus", "Digitalis"),
            result["path"][-1],
        )
        self.assertEqual(
            family["Digitalideae"]["Digitalis"]["list"]["1413"],
            1,
        )

    def test_creates_missing_section_under_existing_genus(self):
        family = _digitalis_family()
        apg = {
            "00_Sectio": "Globiflorae",
            "01_Genus": "Digitalis",
            "02_Tribus": "Digitalideae",
            "03_Familia": "Plantaginaceae",
        }
        result = apg_tree.apply_plant({"Plantaginaceae": family}, apg, 1413)
        section = family["Digitalideae"]["Digitalis"]["Globiflorae"]
        self.assertEqual("Sectio", section["type"])
        self.assertEqual({"1413": 1}, section["list"])
        self.assertIn("Globiflorae", result["created"])
        rebuilt = apg_tree.apg_map_from_path(result["path"])
        self.assertEqual("Globiflorae", rebuilt["00_Sectio"])
        self.assertEqual("Digitalideae", rebuilt["02_Tribus"])


if __name__ == "__main__":
    unittest.main()
