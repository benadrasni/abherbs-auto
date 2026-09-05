"""Inflorescence type classifier. No network, no Firebase."""

import unittest

from plant.inflorescence_type import classify


class ClassifyTests(unittest.TestCase):
    def test_bellis_flowering_head_is_capitulum(self):
        self.assertEqual(
            ["capitulum"],
            classify("Solitary flowering head at the tip of a leafless scape, 15–30 mm across."),
        )
        self.assertEqual(
            ["capitulum"],
            classify("Jednotlivý úbor na vrchole bezlistého stvolu, 15–30 mm v priemere."),
        )

    def test_compound_umbel_beats_umbel(self):
        self.assertEqual(
            ["compound_umbel"],
            classify("Compound umbel, 10-20 secondary umbels. Primary and secondary umbels without bracts."),
        )
        self.assertEqual(
            ["compound_umbel"],
            classify("Zložený okolík, 10–20 okolíčkov. Hlavný okolík aj okolíčky bez listencov."),
        )

    def test_achillea_keeps_capitulum_and_corymb(self):
        self.assertEqual(
            ["capitulum", "corymb"],
            classify("Capitula borne in a dense corymbose cluster."),
        )
        self.assertEqual(
            ["capitulum", "corymb"],
            classify("Úbory v hustej chocholíkovej skupine."),
        )

    def test_clover_is_head_not_capitulum(self):
        self.assertEqual(
            ["head"],
            classify("Stalkless–short-stalked, dense, almost spherical head, often 2 almost united."),
        )
        self.assertEqual(
            ["head"],
            classify("Sediaca alebo krátko stopkatá, hustá, takmer guľovitá hlávka."),
        )

    def test_scorpioid_not_raceme_like(self):
        self.assertEqual(
            ["scorpioid"],
            classify(
                "Flowers in bractless, one-sided scorpioid cymes that uncoil "
                "and elongate into raceme-like clusters."
            ),
        )

    def test_solitary_and_unnamed_are_empty(self):
        self.assertEqual([], classify("Jednotlivý koncový kvet."))
        self.assertEqual([], classify("Erect clusters 4–6 cm across."))
        self.assertEqual(
            [],
            classify("The flowers are monoecious with single-sex wind-pollinated catkins."),
        )
        self.assertEqual([], classify(""))

    def test_common_english_types(self):
        self.assertEqual(["raceme"], classify("A long one-sided terminal raceme."))
        self.assertEqual(["spike"], classify("Dense whorls forming a lax cylindrical spike from the base."))
        self.assertEqual(["spadix"], classify("A slightly arched, 6-10 cm long spadix."))
        self.assertEqual(["corymb"], classify("Terminal corymbs of 15-30 flowers."))
        self.assertEqual(["umbel"], classify("Umbel of 6–20 white flowers on long pedicels."))
        self.assertEqual(["panicle"], classify("A large, much-branched panicle."))
