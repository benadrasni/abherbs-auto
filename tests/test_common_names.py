"""Tests for sourced vernacular names. No network, no Firebase."""

import unittest

from plant import assemble
from plant import common_names
from plant import validate


class CommonNameSourceTests(unittest.TestCase):
    def test_skips_latin_and_does_not_copy_english(self):
        resolved = {
            "accepted_name": "Digitalis lanata",
            "labels": {
                "en": "Digitalis lanata",
                "cs": "náprstník vlnatý",
                "es": "Digitalis lanata",
            },
            "aliases": {"en": ["woolly foxglove"]},
            "wikipedia": {
                "en": "https://en.wikipedia.org/wiki/Digitalis_lanata",
                "fr": "https://fr.wikipedia.org/wiki/Digitale_laineuse",
            },
            "synonyms": [],
        }
        sourced = common_names.collect(resolved)
        self.assertIn("cs", sourced)
        self.assertEqual("náprstník vlnatý", sourced["cs"][0]["name"])
        self.assertEqual("woolly foxglove", sourced["en"][0]["name"])
        self.assertEqual("Digitale laineuse", sourced["fr"][0]["name"])
        self.assertNotIn("es", sourced)
        self.assertNotIn("sk", sourced)
        translations = common_names.translations_from_sources(resolved)
        self.assertEqual("woolly foxglove", translations["en"]["label"])
        self.assertEqual("digitale laineuse", translations["fr"]["label"])
        self.assertNotIn("sk", translations)
        self.assertNotIn("es", translations)

    def test_botanycz_strips_citations(self):
        extract = (
            "Česká jména: náprstník vlnatý (Sloboda 1852, Dostál 1989, Kubát 2002)\n"
            "Slovenská jména: náprstník vlnatý (Reuss 1853, Marhold et Hindák 1998)\n"
            "Čeleď: Plantaginaceae\n"
        )
        names = common_names.from_botanycz_extract(extract)
        self.assertEqual(["náprstník vlnatý"], [item["name"] for item in names["cs"]])
        self.assertEqual(["náprstník vlnatý"], [item["name"] for item in names["sk"]])

    def test_botanycz_slovak_heading_and_latin_aliases(self):
        extract = "České mená: náprstník zrzavý (Sloboda 1852)\n"
        names = common_names.from_botanycz_extract(extract)
        self.assertEqual("náprstník zrzavý", names["cs"][0]["name"])
        self.assertTrue(
            common_names.is_latinish(
                "Lilium carniolicum ssp. jankae",
                "Lilium pyrenaicum",
            )
        )
        self.assertFalse(
            common_names.is_latinish("Azucena del Pirineo", "Lilium pyrenaicum")
        )

    def test_unsourced_translated_english_is_flagged(self):
        sourced = {
            "en": [{"name": "Pyrenean lily", "source": "wikipedia"}],
            "de": [{"name": "Pyrenäen-Lilie", "source": "wikidata"}],
        }
        translations = {
            "en": {"label": "Pyrenean lily"},
            "de": {"label": "Pyrenäen-Lilie"},
            "sk": {"label": "ľalia pyrenejská", "names": ["žltá turbanovitá ľalia"]},
        }
        issues = common_names.unsourced_names(translations, sourced, "Lilium pyrenaicum")
        self.assertIn(("sk", "ľalia pyrenejská"), issues)
        self.assertIn(("sk", "žltá turbanovitá ľalia"), issues)
        self.assertFalse(any(lang == "de" for lang, _ in issues))

    def test_validate_warns_unsourced_names(self):
        packet = {
            "job": {
                "accepted_name": "Lilium pyrenaicum",
                "id": 1417,
                "sourced_names": {
                    "de": [{"name": "Pyrenäen-Lilie", "source": "wikidata"}],
                },
                "photos": {
                    "status": "ok",
                    "roles": ["flower", "leaf", "stem"],
                },
                "illustration": {"ok": True},
            },
            "plants_header": {
                "name": "Lilium pyrenaicum",
                "filterColor": [2],
                "filterHabitat": [1],
                "filterPetal": [3],
                "filterDistribution": [12],
            },
            "plants_v2": {"ipniId": "1"},
            "translations": {
                "en": {
                    "description": "x",
                    "flower": "x",
                    "inflorescence": "x",
                    "fruit": "x",
                    "leaf": "x",
                    "stem": "x",
                    "habitat": "x",
                    "label": "Lilium pyrenaicum",
                },
                "sk": {"label": "ľalia pyrenejská"},
            },
        }
        report = validate.validate(packet)
        self.assertTrue(report["ok"])
        self.assertTrue(
            any("unsourced common names" in item for item in report["warnings"])
        )

    def test_eppo_names_are_sourced(self):
        resolved = {
            "accepted_name": "Digitalis lanata",
            "labels": {"en": "Digitalis lanata"},
            "aliases": {},
            "wikipedia": {},
            "synonyms": [],
        }
        extra = [
            {
                "id": "eppo",
                "url": "https://gd.eppo.int/taxon/DIKLA",
                "names": {
                    "sk": ["náprstník vlnatý"],
                    "es": ["digital lanosa"],
                    "en": ["woolly foxglove"],
                },
            }
        ]
        sourced = common_names.collect(resolved, extra_sources=extra)
        self.assertEqual("náprstník vlnatý", sourced["sk"][0]["name"])
        self.assertEqual("eppo", sourced["sk"][0]["source"])
        self.assertEqual("digital lanosa", sourced["es"][0]["name"])
        issues = common_names.unsourced_names(
            {"sk": {"label": "náprstník vlnatý"}, "es": {"label": "digital lanosa"}},
            sourced,
            "Digitalis lanata",
        )
        self.assertEqual([], issues)

    def test_assemble_still_uses_wikidata_only_for_label(self):
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


if __name__ == "__main__":
    unittest.main()
