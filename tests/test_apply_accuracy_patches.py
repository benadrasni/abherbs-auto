"""Offline tests for scripts.apply_accuracy_patches helpers."""

import unittest

from scripts.apply_accuracy_patches import (
    carry_live_optional_fields,
    carry_live_trivia,
)


class CarryLiveTriviaTests(unittest.TestCase):
    def test_none_payload(self):
        self.assertIsNone(carry_live_trivia({"trivia": "kept"}, None))

    def test_omitted_from_patch(self):
        out = carry_live_trivia(
            {"trivia": "state flower of Kansas"},
            {"description": "A sunflower."},
        )
        self.assertEqual("state flower of Kansas", out["trivia"])
        self.assertEqual("A sunflower.", out["description"])

    def test_live_wins_over_patch(self):
        out = carry_live_trivia(
            {"trivia": "live text"},
            {"trivia": "rewritten", "description": "A sunflower."},
        )
        self.assertEqual("live text", out["trivia"])

    def test_no_live_trivia_leaves_patch(self):
        patch = {"description": "A sunflower."}
        out = carry_live_trivia({}, patch)
        self.assertNotIn("trivia", out)
        out = carry_live_trivia({}, {"description": "A sunflower.", "trivia": "new"})
        self.assertEqual("new", out["trivia"])

    def test_does_not_mutate_patch(self):
        patch = {"description": "A sunflower."}
        carry_live_trivia({"trivia": "kept"}, patch)
        self.assertNotIn("trivia", patch)


class CarryLiveOptionalFieldsTests(unittest.TestCase):
    def test_none_payload(self):
        self.assertIsNone(
            carry_live_optional_fields(
                {"trivia": "kept", "herbalism": "tea"}, None
            )
        )

    def test_copies_trivia_and_herbalism(self):
        out = carry_live_optional_fields(
            {
                "trivia": "state flower of Kansas",
                "herbalism": "Leaves are eaten as a salad.",
            },
            {"description": "A sunflower."},
        )
        self.assertEqual("state flower of Kansas", out["trivia"])
        self.assertEqual("Leaves are eaten as a salad.", out["herbalism"])
        self.assertEqual("A sunflower.", out["description"])

    def test_live_wins_over_patch(self):
        out = carry_live_optional_fields(
            {"trivia": "live trivia", "herbalism": "live uses"},
            {
                "description": "A sunflower.",
                "trivia": "rewritten trivia",
                "herbalism": "rewritten uses",
            },
        )
        self.assertEqual("live trivia", out["trivia"])
        self.assertEqual("live uses", out["herbalism"])

    def test_missing_live_field_leaves_patch(self):
        out = carry_live_optional_fields(
            {"trivia": "kept"},
            {"description": "A sunflower.", "herbalism": "new uses"},
        )
        self.assertEqual("kept", out["trivia"])
        self.assertEqual("new uses", out["herbalism"])

    def test_empty_live_does_not_insert(self):
        out = carry_live_optional_fields({}, {"description": "A sunflower."})
        self.assertNotIn("trivia", out)
        self.assertNotIn("herbalism", out)

    def test_does_not_mutate_patch(self):
        patch = {"description": "A sunflower."}
        carry_live_optional_fields(
            {"trivia": "kept", "herbalism": "tea"}, patch
        )
        self.assertNotIn("trivia", patch)
        self.assertNotIn("herbalism", patch)


if __name__ == "__main__":
    unittest.main()
