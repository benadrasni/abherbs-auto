"""Unit tests for send_notifications helpers. No Firebase, no FCM."""

import os
import tempfile
import unittest

from scripts import send_notifications as sn


class PathAndCountTests(unittest.TestCase):
    def test_list_path(self):
        self.assertEqual("lists_custom/new/2026-08-14/list", sn.list_path("2026-08-14"))

    def test_count_map_and_sparse_list(self):
        self.assertEqual(5, sn.count_ids({"1413": 1, "1414": 1, "1415": 1, "1416": 1, "1417": 1}))
        self.assertEqual(2, sn.count_ids([None, 1, None, 1]))
        self.assertEqual(0, sn.count_ids(None))
        self.assertEqual(0, sn.count_ids([]))


class CopyTests(unittest.TestCase):
    def test_list_copy_plural_and_singular(self):
        title, body = sn.list_copy(5)
        self.assertEqual(sn.DEFAULT_LIST_TITLE, title)
        self.assertEqual("5 species were added. Tap to browse them.", body)
        _, one = sn.list_copy(1)
        self.assertEqual(sn.DEFAULT_LIST_BODY_ONE, one)

    def test_title_appends_official_app_name(self):
        self.assertEqual(
            "New plants — What's that flower?",
            sn.title_with_app_name("New plants", "en"),
        )
        self.assertEqual(
            "Nové rastliny — Čo to tu kvitne?",
            sn.title_with_app_name("Nové rastliny", "sk"),
        )
        self.assertEqual("Čo to tu kvitne?", sn.app_name("sk"))

    def test_list_copy_overrides(self):
        title, body = sn.list_copy(3, title="New flowers", body="{count} new species")
        self.assertEqual("New flowers", title)
        self.assertEqual("3 new species", body)

    def test_plant_copy_uses_sourced_label_placeholder(self):
        title, body = sn.plant_copy("woolly foxglove")
        self.assertEqual("New video available for woolly foxglove", title)
        self.assertEqual(sn.DEFAULT_PLANT_BODY, body)


class PayloadTests(unittest.TestCase):
    def test_list_data_matches_app_action(self):
        self.assertEqual(
            {
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
                "action": "list",
                "path": "lists_custom/new/2026-08-14/list",
            },
            sn.list_data(sn.list_path("2026-08-14")),
        )

    def test_plant_data_keeps_latin_name(self):
        self.assertEqual(
            {
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
                "action": "plant",
                "name": "Lilium pyrenaicum",
            },
            sn.plant_data("Lilium pyrenaicum"),
        )


class ArgsAndLanguagesTests(unittest.TestCase):
    def test_parse_list_and_plant_are_exclusive(self):
        args = sn.parse_args(["--list", "2026-08-14"])
        self.assertEqual("2026-08-14", args.list_date)
        self.assertFalse(args.apply)
        args = sn.parse_args(["--plant", "Digitalis lanata", "--apply", "--lang", "sk"])
        self.assertEqual("Digitalis lanata", args.plant)
        self.assertTrue(args.apply)
        self.assertEqual(["sk"], args.langs)

    def test_parse_browse(self):
        args = sn.parse_args(
            ["--browse", "https://whatsthatflower.com/", "--copy", "data/notifications/web_rebuild.json"]
        )
        self.assertEqual("https://whatsthatflower.com/", args.browse)
        self.assertEqual("data/notifications/web_rebuild.json", args.copy)
        self.assertFalse(args.apply)

    def test_parse_rejects_non_url_browse(self):
        with self.assertRaises(SystemExit):
            sn.parse_args(["--browse", "whatsthatflower.com"])

    def test_parse_rejects_list_and_browse(self):
        with self.assertRaises(SystemExit):
            sn.parse_args(["--list", "2026-08-14", "--browse", "https://whatsthatflower.com/"])

    def test_parse_rejects_bad_date(self):
        with self.assertRaises(SystemExit):
            sn.parse_args(["--list", "14-08-2026"])

    def test_selected_languages(self):
        self.assertEqual({"Slovak": "sk", "Czech": "cs"}, sn.selected_languages(["sk", "cs"]))
        with self.assertRaises(ValueError):
            sn.selected_languages(["xx"])

    def test_parse_uid(self):
        args = sn.parse_args(["--list", "2026-08-14", "--uid", "PGS88GCOzOPJWAaGMyyk66iKXAI3"])
        self.assertEqual("PGS88GCOzOPJWAaGMyyk66iKXAI3", args.uid)

    def test_mask_token(self):
        self.assertEqual("efDzcVzw…wxyz", sn.mask_token("efDzcVzwR8Ku" + "x" * 20 + "wxyz"))


class BrowseCopyTests(unittest.TestCase):
    def test_browse_data_matches_app_action(self):
        self.assertEqual(
            {
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
                "action": "browse",
                "uri": "https://whatsthatflower.com/",
            },
            sn.browse_data("https://whatsthatflower.com/"),
        )

    def test_browse_uri_adds_web_lang(self):
        self.assertEqual(
            "https://whatsthatflower.com/?lang=sk",
            sn.browse_uri("https://whatsthatflower.com/", "sk"),
        )
        self.assertEqual(
            "https://whatsthatflower.com/?lang=zh",
            sn.browse_uri("https://whatsthatflower.com/", "zh-TW"),
        )
        self.assertEqual(
            "https://whatsthatflower.com/?lang=sk",
            sn.browse_uri("https://whatsthatflower.com/?lang=sk", "cs"),
        )

    def test_load_copy_and_missing(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            handle.write('{"en": {"title": "New website", "body": "Tap."}}')
            path = handle.name
        try:
            copy = sn.load_copy(path)
            self.assertEqual(("New website", "Tap."), copy["en"])
            self.assertEqual(["sk"], sn.missing_copy(copy, {"Slovak": "sk"}))
        finally:
            os.remove(path)

    def test_copy_for_language_uses_prepared_and_app_name(self):
        job = {
            "kind": "browse",
            "title": "New website",
            "body": "Tap.",
            "copy": {"sk": ("Nový web", "Ťuknite a pozrite sa.")},
            "uri": "https://whatsthatflower.com/",
        }
        title, body = sn.copy_for_language(job, "sk")
        self.assertEqual("Nový web — Čo to tu kvitne?", title)
        self.assertEqual("Ťuknite a pozrite sa.", body)

    def test_list_copy_for_language_still_appends_app_name(self):
        job = {
            "kind": "list-drop",
            "title": "New plants",
            "body": "5 species were added. Tap to browse them.",
        }
        title, body = sn.copy_for_language(job, "en")
        self.assertEqual("New plants — What's that flower?", title)
        self.assertEqual("5 species were added. Tap to browse them.", body)

    def test_payload_for_language_localizes_browse_uri(self):
        job = {"kind": "browse", "uri": "https://whatsthatflower.com/", "data": sn.browse_data("https://whatsthatflower.com/")}
        self.assertEqual(
            "https://whatsthatflower.com/?lang=sk",
            sn.payload_for_language(job, "sk")["uri"],
        )

    def test_web_rebuild_covers_all_listed_languages(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "notifications", "web_rebuild.json")
        copy = sn.load_copy(path)
        self.assertEqual(set(sn.language_map.values()), set(copy))

    def test_needs_firebase_skips_browse_dry_run(self):
        args = sn.parse_args(["--browse", "https://whatsthatflower.com/"])
        self.assertFalse(sn.needs_firebase(args))
        args = sn.parse_args(["--browse", "https://whatsthatflower.com/", "--apply"])
        self.assertTrue(sn.needs_firebase(args))

    def test_topics_cover_flutter_language_codes(self):
        self.assertEqual(("no", "nb"), sn.topics_for("no"))
        self.assertEqual(("zh-TW", "zh"), sn.topics_for("zh-TW"))
        self.assertEqual(("sk",), sn.topics_for("sk"))


if __name__ == "__main__":
    unittest.main()
