"""Unit tests for send_notifications helpers. No Firebase, no FCM."""

import unittest

import send_notifications as sn


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


if __name__ == "__main__":
    unittest.main()
