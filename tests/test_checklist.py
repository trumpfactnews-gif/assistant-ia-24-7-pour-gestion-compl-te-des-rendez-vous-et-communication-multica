"""Tests des critères d'achat et de vente du §7 du guide."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_scoring import full_metrics  # noqa: E402

from osint_financial import checklist, scoring  # noqa: E402
from osint_financial.macro import MarketRegime  # noqa: E402
from osint_financial.metrics import Metrics  # noqa: E402
from osint_financial.sources.sec import Filing  # noqa: E402
from osint_financial.valuation import DcfResult  # noqa: E402


def favorable_regime() -> MarketRegime:
    regime = MarketRegime(regime="FAVORABLE", score=72.0)
    regime.index_above_sma200 = True
    regime.vix_level = 12.0
    return regime


def alert_filing() -> Filing:
    return Filing(
        form="8-K", filed_at=None, accession="0000320193-26-000064",
        primary_document="a.htm", description="", url=None, items=("1.01",),
    )


class TestEntryChecklist(unittest.TestCase):
    def test_tous_les_criteres_remplis(self) -> None:
        metrics = full_metrics(
            dcf=DcfResult(value_per_share=200.0, upside_pct=45.0),
            alert_filings=[alert_filing()],
        )
        metrics.technical.rsi_14 = 38.0  # pessimisme
        scores = scoring.compute(metrics, macro_score=72.0)
        scores.opportunity_score = 82.0

        result = checklist.entry_checklist(metrics, scores, favorable_regime())
        self.assertTrue(result.satisfied)
        self.assertEqual(result.score, "5/5")

    def test_un_critere_manquant_invalide_la_conjonction(self) -> None:
        metrics = full_metrics(
            dcf=DcfResult(value_per_share=200.0, upside_pct=45.0),
            alert_filings=[alert_filing()],
        )
        metrics.technical.rsi_14 = 70.0  # pas de pessimisme
        metrics.technical.distance_from_high_pct = -1.0
        scores = scoring.compute(metrics, macro_score=72.0)
        result = checklist.entry_checklist(metrics, scores, favorable_regime())
        self.assertFalse(result.satisfied)

    def test_inconnu_nest_pas_un_feu_vert(self) -> None:
        """Une conjonction avec un critère non mesurable reste non satisfaite."""
        metrics = full_metrics(dcf=DcfResult())  # DCF indisponible
        scores = scoring.compute(metrics)
        result = checklist.entry_checklist(metrics, scores, regime=None)
        self.assertFalse(result.satisfied)
        self.assertTrue(result.unmeasurable)
        states = {c.state for c in result.criteria}
        self.assertIn("non mesurable", states)

    def test_macro_absente_est_non_mesurable(self) -> None:
        metrics = full_metrics()
        scores = scoring.compute(metrics)
        result = checklist.entry_checklist(metrics, scores, regime=MarketRegime())
        macro_criterion = next(c for c in result.criteria if "marché" in c.label)
        self.assertIsNone(macro_criterion.met)

    def test_catalyseur_par_achat_dinitie(self) -> None:
        metrics = full_metrics(alert_filings=[])
        scores = scoring.compute(metrics)
        result = checklist.entry_checklist(metrics, scores, favorable_regime())
        catalyst = next(c for c in result.criteria if "Catalyseur" in c.label)
        self.assertTrue(catalyst.met)
        self.assertIn("initié", catalyst.evidence)


class TestExitChecklist(unittest.TestCase):
    def test_surevaluation_declenche(self) -> None:
        metrics = full_metrics(dcf=DcfResult(value_per_share=50.0, upside_pct=-35.0))
        result = checklist.exit_checklist(metrics)
        self.assertTrue(result.satisfied)  # disjonction : un seul critère suffit

    def test_decroissance_declenche(self) -> None:
        metrics = full_metrics(
            dcf=DcfResult(), revenue_growth_yoy_pct=-12.0
        )
        result = checklist.exit_checklist(metrics)
        self.assertTrue(result.satisfied)

    def test_aucun_signal_de_vente(self) -> None:
        metrics = full_metrics(dcf=DcfResult(value_per_share=200.0, upside_pct=40.0))
        result = checklist.exit_checklist(metrics)
        self.assertFalse(result.satisfied)

    def test_moat_declare_non_mesurable(self) -> None:
        result = checklist.exit_checklist(full_metrics())
        moat = next(c for c in result.criteria if "concurrentiel" in c.label)
        self.assertIsNone(moat.met)
        self.assertIn("non mesurable", moat.evidence)

    def test_disjonction_vide_reste_fausse(self) -> None:
        metrics = Metrics(ticker="TEST", company_name="Test")
        result = checklist.exit_checklist(metrics)
        self.assertFalse(result.satisfied)
        self.assertEqual(result.measurable, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
