"""Pure helpers for scripts.rename_plant. No live Firebase."""

import unittest

from scripts.rename_plant import (
    all_genus_firebase_paths,
    divergent_ancestor_paths,
    existing_genus_firebase_path,
    family_firebase_path,
    plan_search_photo_updates,
    public_object_url,
    remapped_catalog_folder,
    resolve_move_paths,
    should_delete_old_gcs_folder,
)


MALVACEAE = {
    "type": "Familia",
    "count": 20,
    "list": {"1029": 1, "340": 1},
    "Malvoideae": {
        "type": "Subfamilia",
        "count": 20,
        "list": {"1029": 1, "340": 1},
        "Lavatera": {
            "type": "Genus",
            "count": 1,
            "list": {"1029": 1},
        },
        "Malveae": {
            "type": "Tribus",
            "count": 10,
            "list": {"340": 1, "341": 1},
            "Malva": {
                "type": "Genus",
                "count": 5,
                "list": {"340": 1, "341": 1, "342": 1, "343": 1, "1205": 1},
                "Malva": {"type": "Sectio", "count": 3, "list": {"342": 1}},
            },
        },
    },
}

MALVA_GENUS = (
    "APG IV_v3/Eukaryota/Plantae/Angiosperms/Mesangiosperms/Eudicots/"
    "Superrosids/Rosids/Malvids/Malvales/Malvaceae/Malvoideae/Malveae/Malva"
)
LAVATERA_LIST = (
    "APG IV_v3/Eukaryota/Plantae/Angiosperms/Mesangiosperms/Eudicots/"
    "Superrosids/Rosids/Malvids/Malvales/Malvaceae/Malvoideae/Lavatera/list"
)


class ExistingGenusTests(unittest.TestCase):
    def test_joins_nested_malva_not_section(self):
        family = (
            "APG IV_v3/Eukaryota/Plantae/Angiosperms/Mesangiosperms/Eudicots/"
            "Superrosids/Rosids/Malvids/Malvales/Malvaceae"
        )
        path = existing_genus_firebase_path(family, MALVACEAE, "Malva")
        self.assertEqual(path, "%s/Malvoideae/Malveae/Malva" % family)

    def test_missing_genus(self):
        family = "APG IV_v3/x/Malvaceae"
        self.assertIsNone(existing_genus_firebase_path(family, MALVACEAE, "Hibiscus"))

    def test_family_path(self):
        apg = {
            "00_Genus": "Lavatera",
            "01_Subfamilia": "Malvoideae",
            "02_Familia": "Malvaceae",
            "03_Ordo": "Malvales",
            "11_Superregnum": "Eukaryota",
        }
        self.assertTrue(family_firebase_path(apg).endswith("/Malvaceae"))
        self.assertTrue(family_firebase_path(apg).startswith("APG IV_v3/Eukaryota"))


CARYOPHYLLACEAE = {
    "type": "Familia",
    "Alsineae": {
        "type": "Tribus",
        "count": 2,
        "list": {"369": 1, "560": 1},
        "Myosoton": {"type": "Genus", "count": 1, "list": {"369": 1}},
        "Stellaria": {"type": "Genus", "count": 1, "list": {"560": 1}},
    },
    "Alsinoideae": {
        "type": "Subfamilia",
        "Alsineae": {
            "type": "Tribus",
            "count": 6,
            "list": {"369": 1, "560": 1, "561": 1, "562": 1, "563": 1, "564": 1},
            "Myosoton": {"type": "Genus", "count": 1, "list": {"369": 1}},
            "Stellaria": {
                "type": "Genus",
                "count": 5,
                "list": {"560": 1, "561": 1, "562": 1, "563": 1, "564": 1},
            },
        },
    },
}


class ResolveMovePathsTests(unittest.TestCase):
    def test_picks_nested_stellaria_and_myosoton(self):
        family = "APG IV_v3/Caryophyllales/Caryophyllaceae"
        apg_parent = family + "/Alsineae"
        resolved = resolve_move_paths(
            family, CARYOPHYLLACEAE, apg_parent, "Myosoton", "Stellaria"
        )
        self.assertEqual(
            resolved["old_path"], family + "/Alsinoideae/Alsineae/Myosoton"
        )
        self.assertEqual(
            resolved["new_path"], family + "/Alsinoideae/Alsineae/Stellaria"
        )
        self.assertEqual(
            resolved["other_old_paths"], [family + "/Alsineae/Myosoton"]
        )
        self.assertTrue(resolved["reused_old"])
        self.assertTrue(resolved["reused_new"])

    def test_all_myosoton_namesakes(self):
        family = "APG IV_v3/Caryophyllales/Caryophyllaceae"
        paths = all_genus_firebase_paths(family, CARYOPHYLLACEAE, "Myosoton")
        self.assertEqual(
            paths,
            [
                family + "/Alsinoideae/Alsineae/Myosoton",
                family + "/Alsineae/Myosoton",
            ],
        )

    def test_new_genus_is_sibling_of_live_old_genus(self):
        """APGIV omitted Malinae; Aria must join Sorbus, not sit on Maleae."""
        family = "APG IV_v3/Rosales/Rosaceae"
        family_node = {
            "type": "Familia",
            "Amygdaloideae": {
                "type": "Subfamilia",
                "Maleae": {
                    "type": "Tribus",
                    "Malinae": {
                        "type": "Subtribus",
                        "Sorbus": {
                            "type": "Genus",
                            "count": 3,
                            "list": {"549": 1, "550": 1, "551": 1},
                            "Aria": {"type": "Subgenus", "count": 1, "list": {"549": 1}},
                        },
                    },
                },
            },
        }
        apg_parent = family + "/Amygdaloideae/Maleae"
        resolved = resolve_move_paths(
            family, family_node, apg_parent, "Sorbus", "Aria"
        )
        self.assertEqual(
            resolved["old_path"], family + "/Amygdaloideae/Maleae/Malinae/Sorbus"
        )
        self.assertEqual(
            resolved["new_path"], family + "/Amygdaloideae/Maleae/Malinae/Aria"
        )
        self.assertTrue(resolved["reused_old"])
        self.assertFalse(resolved["reused_new"])


class SearchPhotoTests(unittest.TestCase):
    def test_increments_existing_malva_token(self):
        photo = {
            "lavatera": {"count": 1, "path": LAVATERA_LIST},
            "malva": {"count": 5, "path": MALVA_GENUS + "/list"},
            "lavatera thuringiaca": {"count": 1, "path": "Lavatera thuringiaca"},
            "malva thuringiaca": {"count": 1, "path": "Lavatera thuringiaca"},
            "m": {
                "06srwg": {"count": 1, "path": LAVATERA_LIST},
                "05cq7h": {"count": 5, "path": MALVA_GENUS + "/list"},
            },
        }
        updates = dict(
            plan_search_photo_updates(
                photo,
                "Lavatera thuringiaca",
                "Malva thuringiaca",
                MALVA_GENUS,
                old_genus_remaining=0,
                deleted_apg_paths=[LAVATERA_LIST[: -len("/list")]],
            )
        )
        self.assertEqual(
            updates["malva"],
            {"count": 6, "path": MALVA_GENUS + "/list"},
        )
        self.assertEqual(
            updates["m/05cq7h"],
            {"count": 6, "path": MALVA_GENUS + "/list"},
        )
        self.assertEqual(updates["lavatera"], {"count": 1, "path": "Malva thuringiaca"})
        self.assertEqual(
            updates["m/06srwg"],
            {"count": 1, "path": "Malva thuringiaca"},
        )
        self.assertEqual(
            updates["malva thuringiaca"],
            {"count": 1, "path": "Malva thuringiaca"},
        )


class DivergentAncestorTests(unittest.TestCase):
    def test_strips_old_subtribe_only(self):
        prefix = (
            "APG IV_v3/Eukaryota/Plantae/Angiosperms/Mesangiosperms/Eudicots/"
            "Superasterids/Asterids/Campanulids/Asterales/Asteraceae/"
            "Cichorioideae/Cichorieae"
        )
        old_path = prefix + "/Hieraciinae/Mycelis"
        new_path = prefix + "/Lactucinae/Lactuca"
        self.assertEqual(
            divergent_ancestor_paths(old_path, new_path),
            [prefix + "/Hieraciinae"],
        )

    def test_same_tribe_is_empty(self):
        prefix = (
            "APG IV_v3/Eukaryota/Plantae/Angiosperms/Mesangiosperms/Eudicots/"
            "Superrosids/Rosids/Malvids/Myrtales/Myrtaceae/Myrtoideae/Myrteae"
        )
        self.assertEqual(
            divergent_ancestor_paths(prefix + "/Acca", prefix + "/Feijoa"),
            [],
        )


class CatalogFolderTests(unittest.TestCase):
    def test_skips_delete_when_photos_already_use_accepted_slug(self):
        plant = {
            "illustrationUrl": (
                "Asterales/Asteraceae/Matricaria_chamomilla/"
                "Matricaria_chamomilla.webp"
            ),
            "photoUrls": [
                "Asterales/Asteraceae/Matricaria_chamomilla/mc1.webp",
            ],
        }
        self.assertEqual(
            remapped_catalog_folder(
                plant, "Matricaria recutita", "Matricaria chamomilla"
            ),
            "Asterales/Asteraceae/Matricaria_chamomilla",
        )
        self.assertFalse(
            should_delete_old_gcs_folder(
                plant, "Matricaria recutita", "Matricaria chamomilla"
            )
        )

    def test_deletes_when_slug_changes(self):
        plant = {
            "illustrationUrl": "Myrtales/Myrtaceae/Acca_sellowiana/Acca_sellowiana.webp",
            "photoUrls": ["Myrtales/Myrtaceae/Acca_sellowiana/as1.webp"],
        }
        self.assertEqual(
            remapped_catalog_folder(plant, "Acca sellowiana", "Feijoa sellowiana"),
            "Myrtales/Myrtaceae/Feijoa_sellowiana",
        )
        self.assertTrue(
            should_delete_old_gcs_folder(plant, "Acca sellowiana", "Feijoa sellowiana")
        )


class PublicUrlTests(unittest.TestCase):
    def test_encodes_hybrid_sign(self):
        url = public_object_url(
            "photos/Malvales/Malvaceae/Hibiscus_×_rosa-sinensis/hr1.webp"
        )
        self.assertIn("Hibiscus_%C3%97_rosa-sinensis", url)
        self.assertTrue(url.startswith("https://storage.googleapis.com/abherbs-resources/"))

    def test_keeps_at_and_slashes(self):
        url = public_object_url(
            "photos/Malvales/Malvaceae/Hibiscus_rosa-sinensis/Hibiscus_rosa-sinensis@400.webp"
        )
        self.assertIn("/Hibiscus_rosa-sinensis@400.webp", url)


if __name__ == "__main__":
    unittest.main()
