"""Unit tests for ingest source clients. No network, no Firebase."""

import json
import os
import tempfile
import unittest

from sources import botanical
from sources import botanycz
from sources import eppo
from sources import gbif
from sources import luontoportti
from sources import ipni
from sources import ipni_overrides
from sources import tdwg
from sources import wcvp
from sources import wikidata


HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")


def _load_json(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


class IpniOverrideTests(unittest.TestCase):
    def test_known_override(self):
        self.assertEqual("508578-1", ipni_overrides.apply("161931-2"))
        self.assertEqual("721172-1", ipni_overrides.apply("30005905-2"))

    def test_passthrough(self):
        self.assertEqual("781250-1", ipni_overrides.apply("781250-1"))
        self.assertEqual("", ipni_overrides.apply(""))
        self.assertIsNone(ipni_overrides.apply(None))


class TdwgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = tdwg.load()

    def test_l3_code_denmark(self):
        self.assertEqual(10, tdwg.l2_for_l3_code("DEN", self.mapping))
        self.assertEqual(10, tdwg.l2_for_l3_code("den", self.mapping))

    def test_l3_name_denmark(self):
        self.assertEqual(10, tdwg.l2_for_l3_name("Denmark", self.mapping))

    def test_acer_native_l3_maps_to_live_native_l2(self):
        native_l3 = [
            "DEN", "GRB", "SWE", "AUT", "BGM", "CZE", "GER", "HUN", "NET",
            "POL", "SWI", "COR", "FRA", "SAR", "SPA", "ALB", "BUL", "GRC",
            "ITA", "ROM", "SIC", "TUE", "YUG", "BLR", "KRY", "UKR", "ALG",
            "NCS", "TCS", "IRN", "TUR",
        ]
        l2 = tdwg.l2_codes_for_l3(native_l3, self.mapping)
        live_native = [10, 11, 12, 13, 14, 20, 33, 34]
        for code in live_native:
            self.assertIn(code, l2)


class WikidataParseTests(unittest.TestCase):
    def test_pick_exact_species(self):
        payload = _load_json("wikidata_search_acer_campestre.json")
        hits = [
            {
                "qid": item.get("id"),
                "label": item.get("label") or "",
                "description": item.get("description") or "",
            }
            for item in payload.get("search") or []
        ]
        picked = wikidata.pick_taxon("Acer campestre", hits)
        self.assertEqual("Q158785", picked["qid"])

    def test_parse_entity_ids(self):
        payload = _load_json("wikidata_Q158785.json")
        entity = payload["entities"]["Q158785"]
        parsed = wikidata.parse_entity(entity)
        self.assertEqual("Q158785", parsed["qid"])
        self.assertEqual("781250-1", parsed["ipni_id"])
        self.assertIsNone(parsed["height_from_cm"])
        self.assertEqual("3189863", parsed["gbif_id"])
        self.assertEqual("ACCA5", parsed["usda_id"])
        self.assertEqual("/m/028j7f", parsed["freebase_id"])
        self.assertEqual("Acer campestre", parsed["taxon_name"])
        self.assertIn("commons", parsed["wikilinks"])
        self.assertIn("species", parsed["wikilinks"])
        self.assertTrue(parsed["wikipedia"].get("en", "").endswith("Acer_campestre"))

    def test_height_quantity(self):
        pair = wikidata._quantity_cm(
            {
                "amount": "+0.60",
                "lowerBound": "+0.30",
                "upperBound": "+1.00",
                "unit": "http://www.wikidata.org/entity/Q11573",
            }
        )
        self.assertEqual((30, 100), pair)


class GbifParseTests(unittest.TestCase):
    def test_match_payload_shape(self):
        payload = _load_json("gbif_match_acer_campestre.json")
        self.assertEqual(3189863, payload["usageKey"])
        self.assertEqual("ACCEPTED", payload["status"])
        self.assertEqual("Sapindaceae", payload["family"])
        self.assertEqual("Sapindales", payload["order"])


class IpniParseTests(unittest.TestCase):
    def test_search_payload(self):
        payload = _load_json("ipni_search_acer_campestre.json")
        first = payload["results"][0]
        self.assertEqual("781250-1", first["id"])
        self.assertEqual("Acer campestre", first["name"])
        self.assertEqual("L.", first["authors"])
        self.assertTrue(first["inPowo"])


class WcvpLookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.db = os.path.join(cls._tmpdir.name, "wcvp.sqlite")
        wcvp.build_sqlite(
            db_path=cls.db,
            names_csv=os.path.join(FIXTURES, "wcvp_names.csv"),
            dist_csv=os.path.join(FIXTURES, "wcvp_distribution.csv"),
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_accepted_name(self):
        row = wcvp.lookup("Acer campestre", db_path=self.db)
        self.assertIsNotNone(row)
        self.assertEqual("Acer campestre", row["accepted_name"])
        self.assertEqual("781250-1", row["ipni_id"])
        self.assertEqual("Sapindaceae", row["family"])
        self.assertEqual("L.", row["author"])
        self.assertEqual("tree", row["lifeform"])

    def test_synonym_resolves(self):
        row = wcvp.lookup("Euacer campestre", db_path=self.db)
        self.assertEqual("Acer campestre", row["accepted_name"])
        self.assertEqual("Synonym", row["query_status"])

    def test_distribution_native_and_introduced(self):
        row = wcvp.lookup("Acer campestre", db_path=self.db)
        live = [10, 11, 12, 13, 14, 20, 33, 34, 72, 75, 76]
        self.assertEqual(live, row["l2"])
        self.assertEqual([10, 11, 12, 13, 14, 20, 33, 34], row["native_l2"])
        self.assertNotIn(74, row["l2"])

    def test_native_only(self):
        row = wcvp.lookup("Acer campestre", db_path=self.db, include_introduced=False)
        self.assertEqual([10, 11, 12, 13, 14, 20, 33, 34], row["l2"])
        self.assertEqual(["DEN", "GER", "FRA", "ITA", "UKR", "ALG", "TCS", "TUR"], row["l3"])

    def test_synonym_list(self):
        row = wcvp.lookup("Acer campestre", db_path=self.db)
        names = [item["name"] for item in row["synonyms"]]
        self.assertIn("Euacer campestre", names)

    def test_unknown_name(self):
        self.assertIsNone(wcvp.lookup("Not a plantus", db_path=self.db))

    def test_l3_through_tdwg_matches_wcvp_l2(self):
        row = wcvp.lookup("Acer campestre", db_path=self.db, include_introduced=False)
        mapped = tdwg.l2_codes_for_l3(row["native_l3"])
        self.assertEqual(row["native_l2"], mapped)


class BotanicalRegistryTests(unittest.TestCase):
    def test_pfaf_url_and_extract_drops_related_plants(self):
        pfaf = next(item for item in botanical.load() if item["id"] == "pfaf")
        self.assertEqual(
            "https://pfaf.org/user/plant.aspx?latinname=Digitalis+lanata",
            botanical.url_for(pfaf, "Digitalis lanata"),
        )
        with open(
            os.path.join(FIXTURES, "botanical", "pfaf_digitalis_lanata.html"),
            encoding="utf-8",
        ) as handle:
            html = handle.read()
        extract = botanical.extract_page(html, pfaf, "Digitalis lanata")
        self.assertIn("Woods and scrub", extract)
        self.assertIn("seeds ripen", extract)
        self.assertNotIn("Lilium canadense", extract)

    def test_lilium_source_only_for_lilium(self):
        lsf = next(
            item for item in botanical.load() if item["id"] == "lilium_species_foundation"
        )
        self.assertTrue(botanical.applies(lsf, "Lilium candidum", genus="Lilium"))
        self.assertFalse(botanical.applies(lsf, "Digitalis lanata", genus="Digitalis"))
        self.assertIn(
            "lilium-candidum",
            botanical.url_for(lsf, "Lilium candidum"),
        )

    def test_missouriplants_url_and_clips_nav_and_lookalikes(self):
        source = next(item for item in botanical.load() if item["id"] == "missouriplants")
        self.assertEqual(
            "https://www.missouriplants.com/Lilium_michiganense_page.html",
            botanical.url_for(source, "Lilium michiganense"),
        )
        with open(
            os.path.join(FIXTURES, "botanical", "missouriplants_lilium_michiganense.html"),
            encoding="utf-8",
        ) as handle:
            html = handle.read()
        extract = botanical.extract_page(html, source, "Lilium michiganense")
        self.assertIn("Family - Liliaceae", extract)
        self.assertIn("prairies", extract)
        self.assertIn("capsules", extract)
        self.assertNotIn("HOME", extract)
        self.assertNotIn("White-Alt", extract)
        self.assertNotIn("superbum", extract)
        self.assertNotIn("Photographs taken", extract)

    def test_hints_skip_pipeline_and_include_pfaf(self):
        hints = botanical.hints_for("Digitalis lanata", genus="Digitalis")
        ids = [item["id"] for item in hints]
        self.assertIn("pfaf", ids)
        self.assertIn("rhs", ids)
        self.assertIn("luontoportti", ids)
        self.assertIn("missouriplants", ids)
        self.assertIn("botanycz", ids)
        self.assertIn("eppo", ids)
        self.assertNotIn("wikipedia", ids)
        self.assertNotIn("lilium_species_foundation", ids)
        reliable = [item["id"] for item in hints if item.get("reliable")]
        self.assertIn("luontoportti", reliable)
        self.assertIn("missouriplants", reliable)
        self.assertIn("botanycz", reliable)
        self.assertIn("eppo", reliable)
        self.assertIn("pfaf", reliable)
        self.assertIn("rhs", reliable)
        botany = next(item for item in hints if item["id"] == "botanycz")
        self.assertEqual(
            "https://botany.cz/cs/digitalis-lanata/",
            botany["url"],
        )


class EppoTests(unittest.TestCase):
    def test_pick_exact_plant_not_hybrid(self):
        lanata = _load_json("botanical/eppo_search_lanata.json")
        self.assertEqual("DIKLA", eppo.pick_hit(lanata, "Digitalis lanata")["e"])
        payload = _load_json("botanical/eppo_search_candidum.json")
        hit = eppo.pick_hit(payload, "Lilium candidum")
        self.assertEqual("LILCA", hit["e"])
        self.assertIsNone(eppo.pick_hit(payload, "Lilium pyrenaicum"))

    def test_parse_names_maps_languages(self):
        with open(
            os.path.join(FIXTURES, "botanical", "eppo_dikla_names.html"),
            encoding="utf-8",
        ) as handle:
            html = handle.read()
        names = eppo.parse_names(html, "Digitalis lanata")
        self.assertEqual(
            ["Grecian foxglove", "woolly foxglove", "yellow turk's cap lily"],
            names["en"],
        )
        self.assertEqual(["náprstník vlnatý"], names["sk"])
        self.assertEqual(["náprstník vlnatý"], names["cs"])
        self.assertEqual(["wolliger Fingerhut"], names["de"])
        self.assertNotIn("es", names)
        self.assertNotIn("ignore me", str(names))


class BotanyCzTests(unittest.TestCase):
    def test_urls_english_then_czech(self):
        self.assertEqual(
            [
                "https://botany.cz/en/digitalis-lanata/",
                "https://botany.cz/cs/digitalis-lanata/",
            ],
            botanycz.urls("Digitalis lanata"),
        )

    def test_extract_clips_photos_and_related_species(self):
        source = next(item for item in botanical.load() if item["id"] == "botanycz")
        with open(
            os.path.join(FIXTURES, "botanical", "botanycz_digitalis_lanata.html"),
            encoding="utf-8",
        ) as handle:
            html = handle.read()
        extract = botanical.extract_page(html, source, "Digitalis lanata")
        self.assertIn("náprstník vlnatý", extract)
        self.assertIn("světlých lesích", extract)
        self.assertIn("kuželovitá tobolka", extract)
        self.assertIn("40–80", extract)
        self.assertNotIn("Fotografovali", extract)
        self.assertNotIn("MUSCARI", extract)
        self.assertNotIn("FERRUGINEA", extract)
        self.assertNotIn("Přeskočit na obsah", extract)
        self.assertNotIn("Categories", extract)


class LuontoporttiTests(unittest.TestCase):
    def test_ignores_article_mention_of_another_species(self):
        payload = _load_json("botanical/luontoportti_find_lanata.json")
        self.assertIsNone(luontoportti.pick_hit(payload, "Digitalis lanata"))

    def test_exact_scientific_name_hit(self):
        payload = _load_json("botanical/luontoportti_find_purpurea.json")
        hit = luontoportti.pick_hit(payload, "Digitalis purpurea")
        self.assertEqual(1712, hit["id"])

    def test_english_article_not_finnish(self):
        page = _load_json("botanical/luontoportti_page_purpurea.json")
        text = luontoportti.extract_text(page, "Digitalis purpurea")
        self.assertIn("Biennial herb", text)
        self.assertIn("Ovate capsule", text)
        self.assertIn("forest margins", text)
        self.assertNotIn("Teriö", text)
        self.assertNotIn("Kukka", text)

    def test_remember_merges_by_id(self):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        try:
            json.dump({"sources": [{"id": "pfaf", "name": "PFAF"}]}, tmp)
            tmp.close()
            botanical.remember(
                {"id": "pfaf", "name": "Plants For A Future", "fetch": "latin"},
                path=tmp.name,
            )
            botanical.remember(
                {"id": "new_flora", "name": "New Flora", "fetch": "manual"},
                path=tmp.name,
            )
            saved = botanical.load(tmp.name)
            self.assertEqual("Plants For A Future", saved[0]["name"])
            self.assertEqual("latin", saved[0]["fetch"])
            self.assertEqual("new_flora", saved[1]["id"])
        finally:
            os.unlink(tmp.name)


class LiveWcvpSmokeTests(unittest.TestCase):
    """Runs only when the full Kew cache has been built."""

    def test_acer_campestre_against_full_cache(self):
        if not os.path.isfile(wcvp.DEFAULT_DB):
            self.skipTest("full WCVP sqlite not built")
        row = wcvp.lookup("Acer campestre")
        self.assertEqual("781250-1", row["ipni_id"])
        self.assertEqual("Sapindaceae", row["family"])
        live_native = [10, 11, 12, 13, 14, 20, 33, 34]
        for code in live_native:
            self.assertIn(code, row["native_l2"])
        mapped = tdwg.l2_codes_for_l3(row["native_l3"])
        for code in live_native:
            self.assertIn(code, mapped)


if __name__ == "__main__":
    unittest.main()
