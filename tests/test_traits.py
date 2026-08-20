"""Trait inference and English draft tests. No network, no Firebase."""

import os
import tempfile
import unittest

from plant import draft_text
from plant import infer_traits
from plant import validate
from sources import wikipedia as wiki_api

ACER_EXTRACT = """Acer campestre, known as the field maple, is a flowering plant species in the family Sapindaceae.

== Description ==
It is a deciduous tree reaching 15–25 m (49–82 ft) tall, with a trunk up to 1 m (3 ft 3 in) in diameter, with finely fissured, often somewhat corky bark. The shoots are brown, with dark brown winter buds. The leaves are in opposite pairs, 5–16 cm long. Usually monoecious, the flowers are produced in spring at the same time as the leaves open, yellow-green, in erect clusters 4–6 cm across. The fruit is a samara with two winged achenes aligned at 180°.

== Distribution ==
The native range of field maple includes much of Europe.
"""

BELLIS_EXTRACT = """Bellis perennis, the daisy, is a European species of the family Asteraceae.

== Description ==
Bellis perennis is a perennial herbaceous plant growing to 20 centimetres (8 inches) in height. The species habitually colonises lawns. The plant blooms from March to September. The flower heads are composite, consisting of many sessile flowers with white ray florets (often tipped red) and yellow disc florets. Each inflorescence is borne on a single leafless stem. The achenes are without pappus.
"""


LANATA_EXTRACT = """Digitalis lanata, vernacularly often called woolly foxglove or Grecian foxglove, is a species of foxglove, a flowering plant in the plantain family Plantaginaceae.

== Description ==
The stems are 0.3 to 0.6 meters in height, or about 13 to 26 inches. The lower cauline leaves are 6 to 12 cm (sometimes to 20 cm) long. The flowers are tubular and bell shaped, pale yellow to whitish with brown or violet lines.

== Ecology ==
The subsequent years, it flowers in June and July, and the seeds ripen in early-mid September. In Ukraine and Moldova it flowers in July and August. It is an invasive species of grasslands and woodlands in Wisconsin.
"""


class InferTests(unittest.TestCase):
    def test_acer_color_habitat_height(self):
        resolved = {"lifeform": "tree", "family": "Sapindaceae", "sources": {}}
        wiki = {"extract": ACER_EXTRACT}
        traits = infer_traits.infer(resolved, wiki)
        self.assertEqual([2, 5], traits["color"]["values"])
        self.assertTrue(traits["color"]["ok"])
        self.assertEqual([6], traits["habitat"]["values"])
        self.assertTrue(traits["habitat"]["ok"])
        self.assertEqual([2], traits["petal"]["values"])
        self.assertEqual(1500, traits["height_from"])
        self.assertEqual(2500, traits["height_to"])
        self.assertEqual(3, traits["flowering_from"])
        self.assertEqual(5, traits["flowering_to"])
        self.assertEqual(0, traits["toxicity_class"])

    def test_bellis_white_composite_lawn(self):
        resolved = {"lifeform": "perennial", "family": "Asteraceae", "sources": {}}
        wiki = {"extract": BELLIS_EXTRACT}
        traits = infer_traits.infer(resolved, wiki)
        self.assertEqual([1], traits["color"]["values"])
        self.assertEqual([1], traits["habitat"]["values"])
        self.assertEqual([3], traits["petal"]["values"])
        self.assertTrue(traits["petal"]["ok"])
        self.assertEqual(20, traits["height_from"])
        self.assertEqual(3, traits["flowering_from"])
        self.assertEqual(9, traits["flowering_to"])

    def test_lanata_best_guesses_from_wikipedia(self):
        resolved = {"lifeform": "biennial or perennial", "family": "Plantaginaceae", "sources": {}}
        traits = infer_traits.infer(resolved, {"extract": LANATA_EXTRACT})
        self.assertEqual([1, 2], traits["color"]["values"])
        self.assertNotIn(4, traits["color"]["values"])
        self.assertTrue(traits["color"]["ok"])
        self.assertEqual([1, 4], traits["habitat"]["values"])
        self.assertTrue(traits["habitat"]["ok"])
        self.assertEqual(30, traits["height_from"])
        self.assertEqual(60, traits["height_to"])
        self.assertEqual(6, traits["flowering_from"])
        self.assertEqual(8, traits["flowering_to"])
        self.assertEqual(4, traits["petal"]["values"][0])

    def test_sisters_fill_gaps_only(self):
        resolved = {"lifeform": "perennial", "family": "Plantaginaceae", "sources": {}}
        sisters = [
            {
                "name": "Digitalis lutea",
                "color": [2],
                "habitat": [1, 4],
                "height_from": 50,
                "height_to": 100,
                "flowering_from": 6,
                "flowering_to": 7,
            },
            {
                "name": "Digitalis grandiflora",
                "color": [2],
                "habitat": [1, 4],
                "height_from": 50,
                "height_to": 130,
                "flowering_from": 6,
                "flowering_to": 9,
            },
            {
                "name": "Digitalis purpurea",
                "color": [3, 4],
                "habitat": [1, 2, 4],
                "height_from": 30,
                "height_to": 150,
                "flowering_from": 6,
                "flowering_to": 8,
            },
        ]
        traits = infer_traits.infer(resolved, {"extract": ""}, sisters=sisters)
        self.assertEqual([2], traits["color"]["values"])
        self.assertEqual([1, 4], traits["habitat"]["values"])
        self.assertEqual(50, traits["height_from"])
        self.assertEqual(130, traits["height_to"])
        self.assertEqual(6, traits["flowering_from"])
        self.assertEqual(8, traits["flowering_to"])
        text_traits = infer_traits.infer(
            resolved, {"extract": LANATA_EXTRACT}, sisters=sisters
        )
        self.assertEqual(30, text_traits["height_from"])
        self.assertEqual([1, 2], text_traits["color"]["values"])

    def test_majority_codes(self):
        self.assertEqual([2], infer_traits.majority_codes([[2], [2], [3, 4]]))
        self.assertEqual([1, 4], infer_traits.majority_codes([[1, 4], [1, 4], [1, 2, 4]]))


class DraftTests(unittest.TestCase):
    def test_splits_and_drafts(self):
        split = wiki_api.split_sections(ACER_EXTRACT)
        self.assertIn("Description", split["sections"])
        english = draft_text.draft_english(
            {"extract": ACER_EXTRACT, "url": "https://en.wikipedia.org/wiki/Acer_campestre"}
        )
        self.assertIn("field maple", english["description"])
        self.assertIn("samara", english["fruit"])
        self.assertIn("leaves", english["leaf"])
        self.assertEqual(
            ["https://en.wikipedia.org/wiki/Acer_campestre"], english["sourceUrls"]
        )

    def test_spike_fills_inflorescence(self):
        english = draft_text.draft_english(
            {
                "extract": "The plant carries spikes of russet, tubular flowers in summer.",
                "url": "https://en.wikipedia.org/wiki/Digitalis_ferruginea",
            }
        )
        self.assertIn("spikes", english["inflorescence"])

    def test_candidum_skips_virus_fruit_and_fills_mandatory(self):
        extract = """Lilium candidum, the Madonna lily or white lily, is a plant in the true lily family. It is native to the Balkans and Middle East.

== Ecology ==
It grows on rocky slopes and in scrub.

== Description ==
It forms bulbs at ground level, and, unlike other lilies, grows a basal rosette of leaves during winter, which die the following summer. A leafy floral stem, which generally grows 1.2 metres tall, emerges in late spring and bears several sweetly and very fragrant flowers in summer. The flowers are pure white and tinted yellow in their throats.

== Toxicity in pets ==
One technique to avoid problems with viruses is to grow plants from seed instead of bulblets.
"""
        english = draft_text.draft_english(
            {"extract": extract, "url": "https://en.wikipedia.org/wiki/Lilium_candidum"},
            resolved={"genus": "Lilium", "family": "Liliaceae", "lifeform": "bulbous geophyte"},
            sisters=[
                {"name": "Lilium martagon", "en": {"fruit": "Spatulate, 3-parted, 6-edged capsule."}},
                {"name": "Lilium bulbiferum", "en": {"fruit": "Obovoid, 6-edged, 3-parted capsule."}},
            ],
        )
        self.assertNotIn("virus", (english.get("fruit") or "").lower())
        self.assertNotIn("bulblet", (english.get("fruit") or "").lower())
        self.assertIn("capsule", english["fruit"].lower())
        self.assertIn("floral stem", english["inflorescence"].lower())
        self.assertNotIn("balkans", (english.get("habitat") or "").lower())
        for field in draft_text.MANDATORY:
            self.assertTrue(english.get(field), "missing %s" % field)
        self.assertNotIn("_draft_missing", english)

    def test_thin_foxglove_gets_short_mandatory_set(self):
        extract = """Digitalis ferruginea, the rusty foxglove, is a species of flowering plant in the family Plantaginaceae, native to Hungary, Romania, Turkey and the Caucasus.

== Description ==
It is a biennial or short-lived perennial plant growing to 1.2 metres in height, which forms a rosette of oblong dark green leaves and carries spikes of russet, tubular flowers in summer.

== Ecology ==
This plant has gained the Royal Horticultural Society's Award of Garden Merit.
"""
        english = draft_text.draft_english(
            {"extract": extract, "url": "https://en.wikipedia.org/wiki/Digitalis_ferruginea"},
            resolved={"genus": "Digitalis", "family": "Plantaginaceae", "lifeform": "perennial"},
            habitat_codes=[1, 2, 4],
        )
        self.assertIn("spikes", english["inflorescence"])
        self.assertIn("capsule", english["fruit"].lower())
        self.assertTrue(english.get("stem"))
        self.assertTrue(english.get("leaf"))
        self.assertLessEqual(len(english["description"]), 900)
        self.assertNotIn("hungary", (english.get("habitat") or "").lower())
        self.assertIn("garden", (english.get("habitat") or "").lower())
        for field in draft_text.MANDATORY:
            self.assertTrue(english.get(field), "missing %s" % field)

    def test_habitat_follows_filter_codes(self):
        extract = """The plant is native to Hungary.

== Ecology ==
It grows in woodland glades and grassland. This plant has gained the Award of Garden Merit.
"""
        english = draft_text.draft_english(
            {"extract": extract, "url": "https://example.test/x"},
            habitat_codes=[1, 2, 4],
        )
        habitat = (english.get("habitat") or "").lower()
        self.assertIn("woodland", habitat)
        self.assertIn("grassland", habitat)
        self.assertIn("garden", habitat)
        self.assertNotIn("hungary", habitat)

    def test_extra_source_fills_habitat_and_fruit(self):
        english = draft_text.draft_english(
            {
                "extract": "Digitalis lanata is a foxglove native to Anatolia.",
                "url": "https://en.wikipedia.org/wiki/Digitalis_lanata",
            },
            habitat_codes=[2, 4],
            extra_sources=[
                {
                    "url": "https://pfaf.org/user/plant.aspx?latinname=Digitalis+lanata",
                    "extract": (
                        "Habitats Woods and scrub. "
                        "It is in flower from June to July, and the seeds ripen in September. "
                        "An easily grown plant, succeeding in ordinary garden soil."
                    ),
                }
            ],
        )
        self.assertIn("woods", (english.get("habitat") or "").lower())
        self.assertIn("garden", (english.get("habitat") or "").lower())
        self.assertNotIn("anatolia", (english.get("habitat") or "").lower())
        self.assertIn("seed", (english.get("fruit") or "").lower())
        self.assertIn(
            "https://pfaf.org/user/plant.aspx?latinname=Digitalis+lanata",
            english["sourceUrls"],
        )

    def test_habitat_does_not_repeat_description(self):
        description = "It is native to Hungary, Romania, Turkey and the Caucasus."
        habitat = (
            "It is native to Hungary, Romania, Turkey and the Caucasus. "
            "This plant has gained the Royal Horticultural Society's Award of Garden Merit."
        )
        trimmed = draft_text._trim_against_description(habitat, description)
        self.assertNotIn("Hungary", trimmed)
        self.assertIn("Award of Garden Merit", trimmed)


class ValidateTests(unittest.TestCase):
    def test_ready_packet(self):
        packet = {
            "job": {
                "accepted_name": "Acer campestre",
                "id": 0,
                "warnings": [],
                "photos": {"status": "ok", "roles": ["flower", "leaf", "fruit"]},
                "illustration": {"ok": True},
                "traits": {
                    "color": {"ok": True, "confidence": 0.8, "values": [5, 2]},
                    "habitat": {"ok": True, "confidence": 0.9, "values": [6]},
                    "petal": {"ok": True, "confidence": 0.6, "values": [2]},
                },
            },
            "plants_header": {
                "filterColor": [5, 2],
                "filterHabitat": [6],
                "filterPetal": [2],
                "filterDistribution": [10, 11],
            },
            "plants_v2": {"ipniId": "781250-1"},
            "translations": {
                "en": {
                    "description": "x",
                    "flower": "x",
                    "inflorescence": "x",
                    "fruit": "x",
                    "leaf": "x",
                    "stem": "x",
                    "habitat": "x",
                }
            },
        }
        report = validate.validate(packet)
        self.assertTrue(report["ok"], report["errors"])

    def test_missing_flower_photo(self):
        packet = {
            "job": {
                "accepted_name": "X",
                "id": 1,
                "photos": {"status": "needs_review", "roles": []},
                "illustration": {"ok": False},
            },
            "plants_header": {
                "filterColor": [],
                "filterHabitat": [],
                "filterPetal": [],
                "filterDistribution": [],
            },
            "plants_v2": {},
            "translations": {},
        }
        report = validate.validate(packet)
        self.assertFalse(report["ok"])
        self.assertTrue(any("photo" in item for item in report["errors"]))

    def test_distribution_map_required_when_job_dir_present(self):
        packet = {
            "job": {
                "accepted_name": "Acer campestre",
                "id": 0,
                "warnings": [],
                "photos": {"status": "ok", "roles": ["flower", "leaf", "fruit"]},
                "illustration": {"ok": True},
            },
            "plants_header": {
                "filterColor": [5],
                "filterHabitat": [6],
                "filterPetal": [2],
                "filterDistribution": [10],
            },
            "plants_v2": {
                "ipniId": "781250-1",
                "illustrationUrl": "Sapindales/Sapindaceae/Acer_campestre/Acer_campestre.webp",
            },
            "translations": {
                "en": {
                    "description": "x",
                    "flower": "x",
                    "inflorescence": "x",
                    "fruit": "x",
                    "leaf": "x",
                    "stem": "x",
                    "habitat": "x",
                }
            },
        }
        tmp = tempfile.TemporaryDirectory()
        try:
            dest = tmp.name
            os.makedirs(os.path.join(dest, "media"))
            packet["dir"] = dest
            report = validate.validate(packet)
            self.assertFalse(report["ok"])
            self.assertTrue(any("distribution map" in item for item in report["errors"]))
            open(
                os.path.join(dest, "media", "Acer_campestre_distribution.webp"),
                "w",
            ).close()
            report = validate.validate(packet)
            self.assertTrue(report["ok"], report["errors"])
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
