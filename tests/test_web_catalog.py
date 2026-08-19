"""Slim web catalog tests. No Firebase."""

import json
import os
import shutil
import tempfile
import unittest

from catalog import incremental_indexes
from catalog import refresh as refresh_indexes
from catalog import web_catalog


ACER_HEADER = {
    "name": "Acer campestre",
    "family": "Sapindaceae",
    "url": "Sapindales/Sapindaceae/Acer_campestre/ac1.webp",
}
ACER_V2 = {
    "id": 0,
    "name": "Acer campestre",
    "illustrationUrl": "Sapindales/Sapindaceae/Acer_campestre/Acer_campestre.webp",
}
VERONICA_HEADER = {
    "name": "Veronica anagallis-aquatica",
    "family": "Plantaginaceae",
    "url": "Lamiales/Plantaginaceae/Veronica_anagallis-aquatica/va1.webp",
}
VERONICA_V2 = {
    "id": 7,
    "name": "Veronica anagallis-aquatica",
    "illustrationUrl": "Lamiales/Plantaginaceae/Veronica_anagallis-aquatica/Veronica_anagallis.webp",
}


class DerivationTests(unittest.TestCase):
    def test_matches_web_header_plate_rule(self):
        self.assertEqual(
            "Sapindales/Sapindaceae/Acer_campestre/Acer_campestre.webp",
            web_catalog.derived_illustration_url(ACER_HEADER["url"]),
        )

    def test_prefers_plants_v2_illustration(self):
        self.assertEqual(
            VERONICA_V2["illustrationUrl"],
            web_catalog.illustration_url(VERONICA_V2, VERONICA_HEADER),
        )

    def test_falls_back_to_derived_plate(self):
        self.assertEqual(
            "Sapindales/Sapindaceae/Acer_campestre/Acer_campestre.webp",
            web_catalog.illustration_url({}, ACER_HEADER),
        )


class PacketTests(unittest.TestCase):
    def test_entry_and_sourced_labels(self):
        packet = {
            "job": {"id": 7, "accepted_name": "Veronica anagallis-aquatica"},
            "plants_header": VERONICA_HEADER,
            "plants_v2": VERONICA_V2,
            "translations": {
                "en": {"label": "blue water-speedwell", "names": ["brook pimpernel"]},
                "de": {"label": "Gauchheil-Ehrenpreis"},
                "la": {"label": "Veronica anagallis-aquatica"},
                "sk-GT": {"label": "nie z tohto zdroja"},
                "fr": {"description": "no vernacular"},
            },
        }
        entry = web_catalog.entry_from_packet(packet)
        self.assertEqual(7, entry["id"])
        self.assertEqual("Veronica anagallis-aquatica", entry["name"])
        self.assertEqual("Plantaginaceae", entry["family"])
        self.assertEqual(VERONICA_HEADER["url"], entry["url"])
        self.assertEqual(VERONICA_V2["illustrationUrl"], entry["illustrationUrl"])
        labels = web_catalog.labels_from_packet(packet)
        self.assertEqual("blue water-speedwell", labels["en"])
        self.assertEqual("Gauchheil-Ehrenpreis", labels["de"])
        self.assertNotIn("la", labels)
        self.assertNotIn("sk-GT", labels)
        self.assertNotIn("fr", labels)

    def test_build_patch_includes_web(self):
        packet = {
            "job": {"id": 0, "accepted_name": "Acer campestre"},
            "plants_header": {
                **ACER_HEADER,
                "filterColor": [5],
                "filterHabitat": [6],
                "filterPetal": [2],
                "filterDistribution": [10],
            },
            "plants_v2": ACER_V2,
            "translations": {"en": {"label": "field maple"}},
            "synonyms": {"ipni": []},
        }
        patch = incremental_indexes.build_patch(packet)
        self.assertEqual(0, patch["web_entry"]["id"])
        self.assertEqual(ACER_V2["illustrationUrl"], patch["web_entry"]["illustrationUrl"])
        self.assertEqual({"en": "field maple"}, patch["web_labels"])


class SlimAndSummaryTests(unittest.TestCase):
    def test_slims_plants_v2(self):
        slim = web_catalog.slim_plants_v2({
            "Acer campestre": {
                "id": 0,
                "illustrationUrl": ACER_V2["illustrationUrl"],
                "photoUrls": ["x"],
                "APGIV": {"01_Familia": "Sapindaceae"},
            }
        })
        self.assertEqual({"id": 0, "illustrationUrl": ACER_V2["illustrationUrl"]}, slim["Acer campestre"])

    def test_summary_covers_expected(self):
        catalog, labels, _ = web_catalog.build_catalog(
            ["Acer campestre"],
            {"0": ACER_HEADER},
            {"Acer campestre": ACER_V2},
            {"en": {"Acer campestre": {"label": "field maple"}}},
        )
        summary = web_catalog.summarize(catalog, labels, expected=1)
        self.assertTrue(summary["covers_expected"])
        self.assertEqual(1, summary["english_labels"])
        self.assertEqual([], summary["missing_illustration"])


class RebuildTests(unittest.TestCase):
    def test_uses_list_index_when_v2_id_disagrees(self):
        catalog, labels, warnings = web_catalog.build_catalog(
            ["Acer campestre", "Veronica anagallis-aquatica"],
            {"0": ACER_HEADER, "1": VERONICA_HEADER},
            {"Acer campestre": ACER_V2, "Veronica anagallis-aquatica": VERONICA_V2},
            {
                "en": {
                    "Acer campestre": {"label": "field maple"},
                    "Veronica anagallis-aquatica": {"label": "blue water-speedwell"},
                },
                "en-GT": {"Acer campestre": {"label": "nope"}},
            },
        )
        self.assertEqual(1, catalog["1"]["id"])
        self.assertEqual(VERONICA_V2["illustrationUrl"], catalog["1"]["illustrationUrl"])
        self.assertNotIn("7", catalog)
        self.assertTrue(any("list index 1" in item for item in warnings))
        self.assertEqual("field maple", labels["en"]["0"])
        self.assertEqual("blue water-speedwell", labels["en"]["1"])
        self.assertNotIn("en-GT", labels)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.input_dir = os.path.join(self.temp, "in")
        self.output_dir = os.path.join(self.temp, "out")
        os.makedirs(os.path.join(self.input_dir, "translations"))
        with open(os.path.join(self.input_dir, "plants_to_update.json"), "w") as handle:
            json.dump(["Acer campestre"], handle)
        with open(os.path.join(self.input_dir, "plants_headers.json"), "w") as handle:
            json.dump({"0": ACER_HEADER}, handle)
        with open(os.path.join(self.input_dir, "plants_v2.json"), "w") as handle:
            json.dump({"Acer campestre": ACER_V2}, handle)
        with open(os.path.join(self.input_dir, "translations", "en.json"), "w") as handle:
            json.dump({"Acer campestre": {"label": "Field Maple"}}, handle)

    def tearDown(self):
        shutil.rmtree(self.temp)

    def test_only_web_writes_local_json(self):
        code = refresh_indexes.main([
            "--input-dir", self.input_dir,
            "--output-dir", self.output_dir,
            "--only", "web",
        ])
        self.assertEqual(0, code)
        with open(os.path.join(self.output_dir, "web_catalog_new.json"), encoding="utf-8") as handle:
            catalog = json.load(handle)
        with open(
            os.path.join(self.output_dir, "web_labels_new", "en.json"), encoding="utf-8"
        ) as handle:
            labels = json.load(handle)
        self.assertEqual("Acer campestre", catalog["0"]["name"])
        self.assertEqual(ACER_V2["illustrationUrl"], catalog["0"]["illustrationUrl"])
        self.assertEqual("Field Maple", labels["0"])
        self.assertFalse(os.path.isfile(os.path.join(self.output_dir, "counts_new.json")))


if __name__ == "__main__":
    unittest.main()
