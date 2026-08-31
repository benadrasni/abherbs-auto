import json
import os
import shutil
import tempfile
import unittest

from catalog import catalog_indexes
from catalog import refresh as refresh_indexes
from scripts import repair_filter_lists


ACER = {
    "name": "Acer campestre",
    "family": "Sapindaceae",
    "filterColor": [5, 2],
    "filterHabitat": [6],
    "filterPetal": [2],
    "filterDistribution": [10, 11],
}

ROSA = {
    "name": "Rosa canina",
    "family": "Rosaceae",
    "filterColor": [3],
    "filterHabitat": [1, 4],
    "filterPetal": [2],
    "filterDistribution": [11],
}


class FilterKeyTests(unittest.TestCase):
    def test_cartesian_size(self):
        keys = catalog_indexes.generate_filter_keys()
        self.assertEqual(11130, len(keys))
        self.assertEqual(11130, catalog_indexes.FILTER_KEY_COUNT)
        self.assertEqual(11130, len(set(keys)))

    def test_empty_and_partial_keys(self):
        self.assertEqual("___", catalog_indexes.filter_key(None, None, None, None))
        self.assertEqual("1_1_1_", catalog_indexes.filter_key("1", "1", "1", None))
        self.assertEqual("_6_2_10", catalog_indexes.filter_key(None, "6", "2", "10"))


class MatchTests(unittest.TestCase):
    def test_multi_color_matches_each_color_and_empty(self):
        self.assertTrue(catalog_indexes.matches_filter(ACER, "___"))
        self.assertTrue(catalog_indexes.matches_filter(ACER, "2___"))
        self.assertTrue(catalog_indexes.matches_filter(ACER, "5___"))
        self.assertFalse(catalog_indexes.matches_filter(ACER, "1___"))
        self.assertTrue(catalog_indexes.matches_filter(ACER, "2_6_2_10"))
        self.assertFalse(catalog_indexes.matches_filter(ACER, "2_1_2_10"))

    def test_matching_keys_agree_with_brute_force(self):
        all_keys = catalog_indexes.generate_filter_keys()
        matched = set(catalog_indexes.matching_keys(ACER))
        brute = {key for key in all_keys if catalog_indexes.matches_filter(ACER, key)}
        self.assertEqual(brute, matched)
        # (empty + 2 colors) * (empty + 1 habitat) * (empty + 1 petal) * (empty + 2 regions)
        self.assertEqual(3 * 2 * 2 * 3, len(matched))

    def test_unknown_habitat_is_ignored(self):
        header = dict(ACER)
        header["filterHabitat"] = [6, 8]
        keys = catalog_indexes.matching_keys(header)
        self.assertTrue(any(key.split("_")[1] == "6" for key in keys))
        self.assertFalse(any(key.split("_")[1] == "8" for key in keys))


class ListingShapeTests(unittest.TestCase):
    def test_dict_and_array_ids(self):
        self.assertEqual({"0", "2"}, catalog_indexes.listing_ids({"0": 1, "1": None, "2": 1}))
        self.assertEqual({"0", "2"}, catalog_indexes.listing_ids([1, None, 1]))
        self.assertEqual(set(), catalog_indexes.listing_ids([]))
        self.assertEqual(set(), catalog_indexes.listing_ids(None))

    def test_token_in_firebase_array(self):
        # Dense lists_4_v2/___DIST nodes come back as [1, 1, ...] not {"0": 1}.
        array_listing = [1, 1, None, 1]
        self.assertTrue(catalog_indexes.listing_has_token(array_listing, "0"))
        self.assertTrue(catalog_indexes.listing_has_token(array_listing, 3))
        self.assertFalse(catalog_indexes.listing_has_token(array_listing, "2"))
        self.assertFalse(catalog_indexes.listing_has_token(array_listing, "5"))
        self.assertFalse("3" in array_listing)


class CountsListsTests(unittest.TestCase):
    def test_builds_maps_with_string_ids(self):
        counts, lists, warnings = catalog_indexes.build_counts_and_lists(
            ["Acer campestre", "Rosa canina"],
            {"0": ACER, "1": ROSA},
        )
        self.assertEqual([], warnings)
        self.assertEqual(11130, len(counts))
        self.assertEqual(2, counts["___"])
        self.assertEqual({"0": 1, "1": 1}, lists["___"])
        self.assertEqual(1, counts["5_6_2_10"])
        self.assertEqual({"0": 1}, lists["5_6_2_10"])
        self.assertEqual(1, counts["3_1_2_11"])
        self.assertEqual({"1": 1}, lists["3_1_2_11"])
        self.assertEqual(0, counts["1_2_3_91"])
        self.assertNotIn("1_2_3_91", lists)

    def test_missing_header_is_warned(self):
        counts, lists, warnings = catalog_indexes.build_counts_and_lists(
            ["Acer campestre"],
            {},
        )
        self.assertEqual(1, len(warnings))
        self.assertEqual(0, counts["___"])
        self.assertEqual({}, lists)


class SearchTests(unittest.TestCase):
    def test_label_and_names(self):
        translations = {
            "Acer campestre": {
                "label": "Field Maple",
                "names": ["Hedge Maple", "field maple"],
            }
        }
        search, warnings = catalog_indexes.build_search_language(
            {"Acer campestre": 0}, translations
        )
        self.assertEqual([], warnings)
        self.assertEqual({"is_label": True, "list": {"0": 1}}, search["field maple"])
        self.assertEqual({"list": {"0": 1}}, search["hedge maple"])

    def test_skips_plants_not_in_catalog(self):
        search, warnings = catalog_indexes.build_search_language(
            {"Acer campestre": 0},
            {"Ghost plant": {"label": "Nope"}},
        )
        self.assertEqual({}, search)
        self.assertEqual([], warnings)

    def test_illegal_keys_are_skipped_and_logged(self):
        search, warnings = catalog_indexes.build_search_language(
            {"Acer campestre": 0},
            {"Acer campestre": {"label": "St. Maple"}},
        )
        self.assertTrue(any("st. maple" in warning for warning in warnings))
        self.assertNotIn("st. maple", search)

    def test_latin_skips_dotted_synonyms(self):
        plants = {
            "Acer campestre": {
                "name": "Acer campestre",
                "synonyms": ["Acer campestre var. leiocarpum", "Acer champavenii"],
            }
        }
        search, warnings = catalog_indexes.build_search_latin(["Acer campestre"], plants)
        self.assertEqual([], warnings)
        self.assertIn("acer campestre", search)
        self.assertTrue(search["acer campestre"]["is_label"])
        self.assertIn("acer champavenii", search)
        self.assertNotIn("acer campestre var. leiocarpum", search)


class PhotoSearchTests(unittest.TestCase):
    def test_apg_and_plants(self):
        apg = {
            "type": "Superregnum",
            "count": 1,
            "Eukaryota": {
                "type": "Regnum",
                "Rosales": {
                    "type": "Ordo",
                    "count": 2.0,
                    "list": True,
                    "freebase": "/m/0ordo",
                    "Rosaceae": {
                        "type": "Familia",
                        "count": 1,
                        "list": True,
                        "freebase": ["/m/fam1", "/m/fam2"],
                    },
                },
            },
        }
        plants = {
            "Rosa canina": {
                "freebaseId": "/m/028j7f,/m/extra",
                "synonyms": ["Rosa ciliatosepala", "Rosales"],
            }
        }
        photo, warnings = catalog_indexes.build_photo_search(
            ["Rosa canina"], plants, apg
        )
        self.assertEqual([], warnings)
        self.assertEqual(
            {"count": 2, "path": "APG IV_v3/Eukaryota/Rosales/list"},
            photo["rosales"],
        )
        self.assertEqual(
            {"count": 1, "path": "APG IV_v3/Eukaryota/Rosales/Rosaceae/list"},
            photo["rosaceae"],
        )
        self.assertNotIn("eukaryota", photo)
        self.assertEqual(photo["m"]["0ordo"], photo["rosales"])
        self.assertEqual(photo["m"]["fam1"], photo["rosaceae"])
        self.assertEqual({"count": 1, "path": "Rosa canina"}, photo["rosa canina"])
        self.assertEqual(photo["m"]["028j7f"], photo["rosa canina"])
        self.assertEqual(photo["m"]["extra"], photo["rosa canina"])
        self.assertEqual({"count": 1, "path": "Rosa canina"}, photo["rosa ciliatosepala"])
        # existing taxon key is not overwritten by a synonym
        self.assertEqual(2, photo["rosales"]["count"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.input_dir = os.path.join(self.temp, "in")
        self.output_dir = os.path.join(self.temp, "out")
        os.makedirs(os.path.join(self.input_dir, "translations"))
        with open(os.path.join(self.input_dir, "plants_to_update.json"), "w") as handle:
            json.dump(["Acer campestre", "Rosa canina"], handle)
        with open(os.path.join(self.input_dir, "plants_headers.json"), "w") as handle:
            json.dump({"0": ACER, "1": ROSA}, handle)
        with open(os.path.join(self.input_dir, "plants_v2.json"), "w") as handle:
            json.dump({
                "Acer campestre": {"name": "Acer campestre", "synonyms": ["Acer champavenii"]},
                "Rosa canina": {"name": "Rosa canina", "freebaseId": "/m/rosa"},
            }, handle)
        with open(os.path.join(self.input_dir, "translations", "en.json"), "w") as handle:
            json.dump({
                "Acer campestre": {"label": "Field Maple"},
                "Rosa canina": {"label": "Dog Rose", "names": ["Briar"]},
            }, handle)
        with open(os.path.join(self.input_dir, "apg_iv_v3.json"), "w") as handle:
            json.dump({
                "Rosales": {
                    "type": "Ordo",
                    "count": 1,
                    "list": True,
                    "Rosaceae": {"type": "Familia", "count": 1, "list": True},
                }
            }, handle)

    def tearDown(self):
        shutil.rmtree(self.temp)

    def test_writes_local_json_only(self):
        code = refresh_indexes.main([
            "--input-dir", self.input_dir,
            "--output-dir", self.output_dir,
        ])
        self.assertEqual(0, code)

        def load(relative):
            with open(os.path.join(self.output_dir, relative), encoding="utf-8") as handle:
                return json.load(handle)

        counts = load("counts_new.json")
        lists = load("lists_new.json")
        en = load(os.path.join("search_new", "en.json"))
        latin = load(os.path.join("search_new", "la.json"))
        photo = load("search_photo_new.json")
        summary = load("summary.json")
        self.assertEqual(11130, len(counts))
        self.assertEqual(2, counts["___"])
        self.assertEqual({"0": 1, "1": 1}, lists["___"])
        self.assertTrue(en["field maple"]["is_label"])
        self.assertEqual({"0": 1}, en["field maple"]["list"])
        self.assertIn("acer champavenii", latin)
        self.assertEqual("Rosa canina", photo["rosa canina"]["path"])
        self.assertEqual(False, summary["firebase_writes"])
        self.assertEqual(2, summary["web_entries"])
        self.assertEqual(["en"], summary["web_label_languages"])
        web_catalog = load("web_catalog_new.json")
        self.assertEqual("Acer campestre", web_catalog["0"]["name"])
        self.assertEqual("Rosa canina", web_catalog["1"]["name"])
        self.assertEqual("Field Maple", load(os.path.join("web_labels_new", "en.json"))["0"])
        self.assertNotIn("firebase_admin", refresh_indexes.__dict__)
        self.assertNotIn("requests", refresh_indexes.__dict__)

    def test_normalize_plant_list_shapes(self):
        self.assertEqual(["A", "B"], refresh_indexes.normalize_plant_list(["A", "B"]))
        self.assertEqual(
            ["A", "B"],
            refresh_indexes.normalize_plant_list({"count": 2, "list": ["A", "B"]}),
        )
        self.assertEqual(
            ["A", "B"],
            refresh_indexes.normalize_plant_list({"1": "B", "0": "A", "count": 2}),
        )


class RepairFilterListsTests(unittest.TestCase):
    def test_finds_leftover_on_firebase_array_list(self):
        names = ["Acer campestre", "Rosa canina"]
        headers = [ACER, ROSA]
        lists = {
            "___10": [1, 1],
            "2_6_2_10": {"0": 1},
            "3_1_2_11": {"1": 1},
        }
        extras = repair_filter_lists.find_extras(names, headers, lists)
        leftover = {(row["id"], row["key"]) for row in extras}
        self.assertEqual({(1, "___10")}, leftover)


if __name__ == "__main__":
    unittest.main()
